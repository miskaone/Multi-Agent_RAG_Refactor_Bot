"""Planner agent for task decomposition."""

import os
import re
import json
from typing import Any, Literal

from anthropic import Anthropic
import openai

from refactor_bot.agents.exceptions import (
    AgentError,
    DirectiveValidationError,
    PlanningError,
    TaskDependencyError,
)
from refactor_bot.models import RepoIndex, RetrievalResult, TaskNode, TaskStatus
from refactor_bot.rules import REACT_RULES, select_applicable_rules
from refactor_bot.skills.registry import registry

MAX_DIRECTIVE_LENGTH = 2000
MAX_FILES_IN_PROMPT = 50
MAX_CONTEXT_IN_PROMPT = 10
MAX_SOURCE_PREVIEW = 200
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0

# Prompt injection patterns - case-insensitive substring matches
_INJECTION_SUBSTRINGS = [
    "ignore previous",
    "ignore above",
    "ignore all",
    "disregard previous",
    "disregard above",
    "disregard all",
    "forget previous",
    "forget above",
    "forget your",
    "system prompt",
    "you are now",
    "new instructions",
    "override instructions",
    "act as",
    "pretend you",
    "jailbreak",
    "do anything now",
]

# Regex patterns for structural injection markers
_INJECTION_REGEXES = [
    re.compile(r"<\|"),          # token boundary markers
    re.compile(r"\|>"),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"<<SYS>>", re.IGNORECASE),
    re.compile(r"<</SYS>>", re.IGNORECASE),
    re.compile(r"```\s*system", re.IGNORECASE),  # markdown system block
]


class Planner:
    """Decomposes refactor directives into structured task DAGs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "auto",
        llm_fallback_provider: str | None = None,
        allow_fallback: bool = False,
        allow_human_fallback: bool = False,
    ):
        """Initialize the planner.

        Args:
            api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var)
            model: Model ID to use for planning

        Raises:
            AgentError: If no API key is found
        """
        self.model = model
        self.api_key: str | None = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        )
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.llm_provider: Literal["anthropic", "openai", "auto"] = "auto"
        self.llm_fallback_provider: str | None = None
        self.allow_fallback: bool = False
        self.allow_human_fallback: bool = False
        self._anthropic_client: Anthropic | None = None
        self._openai_client: openai.OpenAI | None = None
        if self.api_key:
            self._anthropic_client = Anthropic(api_key=self.api_key)
        if self.openai_api_key:
            self._openai_client = openai.OpenAI(api_key=self.openai_api_key)
        if not (self._anthropic_client or self._openai_client):
            raise AgentError(
                "No Anthropic or OpenAI API key found. "
                "Provide via parameters, ANTHROPIC_API_KEY, CLAUDE_CODE_OAUTH_TOKEN, "
                "or OPENAI_API_KEY env vars."
            )
        self.set_provider_config(
            llm_provider=llm_provider,
            llm_fallback_provider=llm_fallback_provider,
            allow_fallback=allow_fallback,
            allow_human_fallback=allow_human_fallback,
        )

    def _normalize_provider(
        self,
        value: str,
    ) -> Literal["anthropic", "openai", "auto"]:
        if value not in {"auto", "anthropic", "openai"}:
            raise PlanningError(f"Unsupported provider: {value}")
        return value

    def set_provider_config(
        self,
        llm_provider: str = "auto",
        llm_fallback_provider: str | None = None,
        allow_fallback: bool = False,
        allow_human_fallback: bool = False,
    ) -> None:
        self.llm_provider = self._normalize_provider(llm_provider)
        self.llm_fallback_provider = (
            self._normalize_provider(llm_fallback_provider)
            if llm_fallback_provider
            else None
        )
        self.allow_fallback = bool(allow_fallback)
        self.allow_human_fallback = bool(allow_human_fallback)

        if self.llm_provider == "anthropic" and self._anthropic_client is None:
            raise PlanningError(
                "No Anthropic API key found for --llm-provider=anthropic."
            )
        if self.llm_provider == "openai" and self._openai_client is None:
            raise PlanningError(
                "No OpenAI API key found for --llm-provider=openai."
            )
        if self.allow_fallback and self.llm_fallback_provider:
            if self.llm_fallback_provider == "anthropic" and self._anthropic_client is None:
                raise PlanningError(
                    "Fallback provider requested as anthropic but ANTHROPIC_API_KEY is not set."
                )
            if self.llm_fallback_provider == "openai" and self._openai_client is None:
                raise PlanningError(
                    "Fallback provider requested as openai but OPENAI_API_KEY is not set."
                )

    def _primary_provider(self) -> Literal["anthropic", "openai"]:
        if self.llm_provider == "auto":
            if self._anthropic_client is not None:
                return "anthropic"
            return "openai"
        return self.llm_provider

    def _resolve_model(self, provider: str) -> str:
        if provider == "openai" and self.model.startswith("claude-"):
            return "gpt-4o-mini"
        return self.model

    def _provider_chain(self) -> list[str]:
        chain: list[str] = [self._primary_provider()]
        if self.allow_fallback and self.llm_fallback_provider:
            fallback = self.llm_fallback_provider
            if fallback != chain[0]:
                chain.append(fallback)
        return chain

    def _prompt_fallback(self, error: Exception, fallback_provider: str) -> bool:
        if not self.allow_human_fallback:
            return False
        try:
            prompt = (
                f"Planner call failed with {type(error).__name__}: {error} "
                f"\nUse fallback provider '{fallback_provider}'? [y/N]: "
            )
            response = input(prompt).strip().lower()
            return response in {"y", "yes"}
        except EOFError:
            return False

    def _get_openai_tool_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema.get("description", ""),
                "parameters": schema.get("input_schema", {}),
            },
        }

    def _parse_openai_tool_payload(self, response: Any) -> dict[str, Any]:
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            raise PlanningError("No tool call found in OpenAI response")
        call = tool_calls[0]
        if getattr(call, "type", "function") != "function":
            raise PlanningError("OpenAI tool call type is not function")
        arguments = json.loads(call.function.arguments or "{}")
        if "tasks" not in arguments:
            raise PlanningError("OpenAI response missing 'tasks' in tool arguments")
        return arguments

    def _to_task_nodes(self, tool_input: dict[str, Any]) -> list[TaskNode]:
        tasks = []
        for task_data in tool_input.get("tasks", []):
            raw_confidence = task_data.get("confidence_score")
            if raw_confidence is not None:
                confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, float(raw_confidence)))
            else:
                confidence = None
            tasks.append(
                TaskNode(
                    task_id=task_data["task_id"],
                    description=task_data["description"],
                    affected_files=task_data["affected_files"],
                    dependencies=task_data.get("dependencies", []),
                    confidence_score=confidence,
                    status=TaskStatus.PENDING,
                )
            )
        return tasks

    def decompose(
        self, directive: str, repo_index: RepoIndex, context: list[RetrievalResult]
    ) -> list[TaskNode]:
        """Decompose a refactor directive into tasks.

        Args:
            directive: The user's refactor directive
            repo_index: Repository index with file information
            context: Retrieval results providing relevant code context

        Returns:
            List of TaskNode objects representing the refactor plan

        Raises:
            DirectiveValidationError: If directive is invalid or potentially malicious
            PlanningError: If task decomposition fails or tasks have no valid files
            TaskDependencyError: If dependencies form cycles or reference missing tasks
        """
        # Step 1: Validate directive
        self._validate_directive(directive)

        # Step 2: Get applicable rules
        is_react = repo_index.is_react_project
        applicable_rule_ids = select_applicable_rules(directive, is_react)
        applicable_rules = [rule for rule in REACT_RULES if rule.rule_id in applicable_rule_ids]
        # Merge in active skill rule IDs for forward compatibility
        skill_rules = registry.get_all_rules()
        applicable_rule_ids.extend(
            [rule.rule_id for rule in skill_rules if rule.rule_id not in applicable_rule_ids]
        )

        # Step 3: Build prompt with skill prompt-context if any are active
        skill_context = registry.get_prompt_context_for_all_active(directive)
        prompt = self._build_prompt(
            directive=directive,
            repo_index=repo_index,
            context=context,
            applicable_rules=applicable_rules,
            skill_context=skill_context,
        )

        # Step 4: Call LLM API with tool-use
        response = None
        used_provider: str = ""
        providers = self._provider_chain()
        last_error: Exception | None = None
        tool_schema = self._get_tool_schema()
        for index, provider in enumerate(providers):
            try:
                if provider == "anthropic":
                    if not self._anthropic_client:
                        raise PlanningError("Anthropic client unavailable")
                    response = self._anthropic_client.messages.create(
                        model=self._resolve_model("anthropic"),
                        max_tokens=4096,
                        tools=[tool_schema],
                        messages=[{"role": "user", "content": prompt}],
                    )
                else:
                    if not self._openai_client:
                        raise PlanningError("OpenAI client unavailable")
                    response = self._openai_client.chat.completions.create(
                        model=self._resolve_model("openai"),
                        max_tokens=4096,
                        tools=[self._get_openai_tool_schema(tool_schema)],
                        tool_choice={"type": "function", "function": {"name": "create_task_plan"}},
                        messages=[{"role": "user", "content": prompt}],
                    )
                used_provider = provider
                break
            except Exception as error:
                last_error = error
                if index >= len(providers) - 1:
                    break
                if not self.allow_fallback and not self.allow_human_fallback:
                    break
                if not self._prompt_fallback(error, providers[index + 1]):
                    break

        if response is None:
            raise PlanningError(f"Failed to call planner LLM: {last_error}") from last_error

        # Step 5: Parse tool-use response
        if used_provider == "openai":
            tasks = self._to_task_nodes(self._parse_openai_tool_payload(response))
        else:
            tasks = self._parse_tool_response(response)

        # Step 6: Validate file paths
        tasks = self._validate_file_paths(tasks, repo_index)

        # Step 7: Validate dependencies
        self._validate_dependencies(tasks)

        # Step 8: Attach applicable rules
        for task in tasks:
            task.applicable_rules = applicable_rule_ids

        return tasks

    def _validate_directive(self, directive: str) -> None:
        """Validate that the directive is safe and well-formed.

        Args:
            directive: The user's refactor directive

        Raises:
            DirectiveValidationError: If directive is invalid or malicious
        """
        # Check empty or whitespace-only
        if not directive or not directive.strip():
            raise DirectiveValidationError("Directive cannot be empty or whitespace-only")

        # Check length
        if len(directive) > MAX_DIRECTIVE_LENGTH:
            raise DirectiveValidationError(
                f"Directive exceeds maximum length of {MAX_DIRECTIVE_LENGTH} characters"
            )

        # Check for prompt injection patterns (case-insensitive substrings)
        directive_lower = directive.lower()
        for pattern in _INJECTION_SUBSTRINGS:
            if pattern in directive_lower:
                raise DirectiveValidationError(
                    f"Directive contains potentially malicious pattern: '{pattern}'"
                )

        # Check for structural injection markers (regex)
        for regex in _INJECTION_REGEXES:
            if regex.search(directive):
                raise DirectiveValidationError(
                    "Directive contains potentially malicious markup"
                )

    def _build_prompt(
        self,
        directive: str,
        repo_index: RepoIndex,
        context: list[RetrievalResult],
        applicable_rules: list[Any],
        skill_context: str = "",
    ) -> str:
        """Build the prompt for Claude API.

        Args:
            directive: User's refactor directive
            repo_index: Repository index
            context: Retrieval results
            applicable_rules: Rules that apply to this project

        Returns:
            Formatted prompt string
        """
        # Build file list summary
        file_paths = [f.relative_path for f in repo_index.files[:MAX_FILES_IN_PROMPT]]
        file_list = "\n".join(f"- {path}" for path in file_paths)
        if len(repo_index.files) > MAX_FILES_IN_PROMPT:
            file_list += f"\n... and {len(repo_index.files) - MAX_FILES_IN_PROMPT} more files"

        # Build context summary
        context_summary = ""
        for i, result in enumerate(context[:MAX_CONTEXT_IN_PROMPT], 1):
            context_summary += f"\n{i}. {result.file_path} (score: {result.similarity:.3f})\n"
            context_summary += f"   {result.source_code[:MAX_SOURCE_PREVIEW]}...\n"

        # Build rules summary
        rules_summary = ""
        if applicable_rules:
            rules_summary = "\n\nApplicable React Performance Rules:\n"
            for rule in applicable_rules:
                rules_summary += f"\n- {rule.rule_id} ({rule.priority}): {rule.description}\n"

        skill_instructions = ""
        if skill_context:
            skill_instructions = "\n\nSkill Context:\n" + skill_context

        prompt = f"""You are a refactoring assistant. Your task is to decompose the following \
refactoring directive into a structured task plan.

Directive: {directive}

Repository Information:
- Total files: {len(repo_index.files)}
- React project: {repo_index.is_react_project}

Sample files in repository:
{file_list}

Relevant code context:
{context_summary}
{rules_summary}
{skill_instructions}

Your task:
1. Break down the directive into atomic refactoring tasks
2. Each task should affect specific files
3. Identify dependencies between tasks (if task B requires task A to be completed first)
4. Assign a confidence score (0.0-1.0) for each task based on available context

Use the create_task_plan tool to structure your response.
"""

        return prompt

    def _get_tool_schema(self) -> dict[str, Any]:
        """Get the tool schema for Claude API.

        Returns:
            Tool schema dictionary
        """
        return {
            "name": "create_task_plan",
            "description": "Create a structured task plan for refactoring",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {
                                    "type": "string",
                                    "description": "Unique identifier for the task",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Clear description of what this task does",
                                },
                                "affected_files": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of file paths that will be modified",
                                },
                                "dependencies": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": (
                                        "List of task_ids that must complete before this task"
                                    ),
                                },
                                "confidence_score": {
                                    "type": "number",
                                    "description": "Confidence score between 0.0 and 1.0",
                                },
                            },
                            "required": [
                                "task_id",
                                "description",
                                "affected_files",
                                "confidence_score",
                            ],
                        },
                    }
                },
                "required": ["tasks"],
            },
        }

    def _parse_tool_response(self, response: Any) -> list[TaskNode]:
        """Parse Claude API response into TaskNode objects.

        Args:
            response: Claude API response

        Returns:
            List of TaskNode objects

        Raises:
            PlanningError: If response parsing fails
        """
        # Find tool use in response
        tool_use = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "create_task_plan":
                tool_use = block
                break

        if not tool_use:
            raise PlanningError("No tool_use block found in Claude response")

        try:
            # Parse tool input
            tool_input = tool_use.input
            tasks_data = tool_input.get("tasks", [])

            if not tasks_data:
                raise PlanningError("No tasks returned in tool response")

            # Convert to TaskNode objects
            tasks = []
            for task_data in tasks_data:
                # Validate and clamp confidence score
                raw_confidence = task_data.get("confidence_score")
                if raw_confidence is not None:
                    confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, float(raw_confidence)))
                else:
                    confidence = None

                task = TaskNode(
                    task_id=task_data["task_id"],
                    description=task_data["description"],
                    affected_files=task_data["affected_files"],
                    dependencies=task_data.get("dependencies", []),
                    confidence_score=confidence,
                    status=TaskStatus.PENDING,
                )
                tasks.append(task)

            return tasks

        except Exception as e:
            raise PlanningError(f"Failed to parse tool response: {e}") from e

    def _validate_file_paths(
        self, tasks: list[TaskNode], repo_index: RepoIndex
    ) -> list[TaskNode]:
        """Validate and filter file paths against repository index.

        Args:
            tasks: List of tasks to validate
            repo_index: Repository index with valid file paths

        Returns:
            List of tasks with validated file paths

        Raises:
            PlanningError: If any task has zero valid files after filtering
        """
        # Build set of valid paths (both absolute and relative)
        valid_paths = set()
        for file_info in repo_index.files:
            valid_paths.add(file_info.file_path)
            valid_paths.add(file_info.relative_path)

        # Validate and filter each task
        for task in tasks:
            valid_files = [f for f in task.affected_files if f in valid_paths]

            if not valid_files:
                raise PlanningError(
                    f"Task '{task.task_id}' has 0 valid files after filtering. "
                    f"Original files: {task.affected_files}"
                )

            task.affected_files = valid_files

        return tasks

    def _validate_dependencies(self, tasks: list[TaskNode]) -> None:
        """Validate task dependencies for cycles and missing references.

        Args:
            tasks: List of tasks to validate

        Raises:
            TaskDependencyError: If dependencies are invalid
        """
        # Build task ID set
        task_ids = {task.task_id for task in tasks}

        # Check for missing dependency references
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    raise TaskDependencyError(
                        f"Task '{task.task_id}' depends on missing task '{dep_id}'"
                    )

        # Check for cycles using DFS
        def has_cycle(task_id: str, visited: set[str], rec_stack: set[str]) -> bool:
            """DFS-based cycle detection."""
            visited.add(task_id)
            rec_stack.add(task_id)

            # Find task
            task = next((t for t in tasks if t.task_id == task_id), None)
            if not task:
                return False

            # Check dependencies
            for dep_id in task.dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id, visited, rec_stack):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        visited: set[str] = set()
        for task in tasks:
            if task.task_id not in visited:
                if has_cycle(task.task_id, visited, set()):
                    raise TaskDependencyError(
                        f"Cyclic dependency detected involving task '{task.task_id}'"
                    )

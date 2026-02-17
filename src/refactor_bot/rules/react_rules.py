"""React performance optimization rules."""

from refactor_bot.rules.rule_engine import ReactRule

REACT_RULES = [
    # Category 1: Eliminating Waterfalls (CRITICAL)
    ReactRule(
        rule_id="async-defer-await",
        category="Eliminating Waterfalls",
        priority="CRITICAL",
        description=(
            "Avoid blocking the main thread with synchronous await "
            "in component initialization"
        ),
        incorrect_pattern="""
// Component waits for async operation before rendering
async function MyComponent() {
    const data = await fetchUserData();  // Blocks rendering
    return <div>{data.name}</div>;
}
""",
        correct_pattern="""
// Use React Query or SWR to defer and cache
function MyComponent() {
    const { data, isLoading } = useQuery('user', fetchUserData);
    if (isLoading) return <Spinner />;
    return <div>{data.name}</div>;
}
""",
    ),
    ReactRule(
        rule_id="async-parallel",
        category="Eliminating Waterfalls",
        priority="CRITICAL",
        description="Fetch data in parallel, not sequentially",
        incorrect_pattern="""
// Sequential fetches create waterfall
async function loadData() {
    const user = await fetchUser();
    const posts = await fetchPosts();     // Waits for user
    const comments = await fetchComments(); // Waits for posts
    return { user, posts, comments };
}
""",
        correct_pattern="""
// Parallel fetches complete faster
async function loadData() {
    const [user, posts, comments] = await Promise.all([
        fetchUser(),
        fetchPosts(),
        fetchComments()
    ]);
    return { user, posts, comments };
}
""",
    ),
    ReactRule(
        rule_id="async-dependencies",
        category="Eliminating Waterfalls",
        priority="CRITICAL",
        description="Only await when there's a true dependency",
        incorrect_pattern="""
// Waits unnecessarily for userId when other fetches are independent
async function loadDashboard(userId: string) {
    const user = await fetchUser(userId);
    const posts = await fetchPosts(userId);  // Could start earlier
    const analytics = await fetchAnalytics(); // No dependency on userId
}
""",
        correct_pattern="""
// Start all fetches immediately, await only when needed
async function loadDashboard(userId: string) {
    const analyticsPromise = fetchAnalytics(); // Start immediately
    const [user, posts] = await Promise.all([
        fetchUser(userId),
        fetchPosts(userId)
    ]);
    const analytics = await analyticsPromise;
}
""",
    ),
    ReactRule(
        rule_id="async-api-routes",
        category="Eliminating Waterfalls",
        priority="CRITICAL",
        description="Parallelize independent database queries in API routes",
        incorrect_pattern="""
// API route with sequential database queries
export async function GET(request: Request) {
    const user = await db.user.findUnique({ where: { id } });
    const posts = await db.post.findMany({ where: { authorId: id } });
    const followers = await db.follow.count({ where: { followingId: id } });
    return Response.json({ user, posts, followers });
}
""",
        correct_pattern="""
// Parallel database queries reduce latency
export async function GET(request: Request) {
    const [user, posts, followers] = await Promise.all([
        db.user.findUnique({ where: { id } }),
        db.post.findMany({ where: { authorId: id } }),
        db.follow.count({ where: { followingId: id } })
    ]);
    return Response.json({ user, posts, followers });
}
""",
    ),
    ReactRule(
        rule_id="async-suspense-boundaries",
        category="Eliminating Waterfalls",
        priority="CRITICAL",
        description="Use Suspense boundaries to avoid parent-child waterfalls",
        incorrect_pattern="""
// Parent waits for child before streaming
async function ParentComponent() {
    const parentData = await fetchParent();
    return (
        <div>
            <h1>{parentData.title}</h1>
            <ChildComponent />  {/* Child blocks parent */}
        </div>
    );
}

async function ChildComponent() {
    const childData = await fetchChild();
    return <div>{childData.content}</div>;
}
""",
        correct_pattern="""
// Suspense allows parent to render while child loads
function ParentComponent() {
    return (
        <div>
            <h1>{use(fetchParent()).title}</h1>
            <Suspense fallback={<Spinner />}>
                <ChildComponent />
            </Suspense>
        </div>
    );
}

function ChildComponent() {
    const childData = use(fetchChild());
    return <div>{childData.content}</div>;
}
""",
    ),
    # Category 2: Bundle Size Optimization (CRITICAL)
    ReactRule(
        rule_id="bundle-barrel-imports",
        category="Bundle Size Optimization",
        priority="CRITICAL",
        description="Avoid barrel imports that prevent tree-shaking",
        incorrect_pattern="""
// Imports entire lodash library
import { debounce } from 'lodash';

// Imports all Material-UI components
import { Button, TextField } from '@mui/material';
""",
        correct_pattern="""
// Import only the specific function
import debounce from 'lodash/debounce';

// Import only specific components
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
""",
    ),
    ReactRule(
        rule_id="bundle-dynamic-imports",
        category="Bundle Size Optimization",
        priority="CRITICAL",
        description="Use dynamic imports for code-splitting heavy components",
        incorrect_pattern="""
// Heavy chart library loaded on every page
import { Chart } from 'chart.js';
import { MarkdownEditor } from 'heavy-editor';

function Dashboard() {
    const [showChart, setShowChart] = useState(false);
    return <div>{showChart && <Chart data={data} />}</div>;
}
""",
        correct_pattern="""
// Chart library only loaded when needed
const Chart = lazy(() => import('chart.js').then(m => ({ default: m.Chart })));
const MarkdownEditor = lazy(() => import('heavy-editor'));

function Dashboard() {
    const [showChart, setShowChart] = useState(false);
    return (
        <div>
            {showChart && (
                <Suspense fallback={<Spinner />}>
                    <Chart data={data} />
                </Suspense>
            )}
        </div>
    );
}
""",
    ),
    ReactRule(
        rule_id="bundle-defer-third-party",
        category="Bundle Size Optimization",
        priority="CRITICAL",
        description="Defer third-party scripts until after initial render",
        incorrect_pattern="""
// Analytics blocks initial render
import Analytics from '@segment/analytics-next';

function App() {
    Analytics.track('page_view');  // Loaded in main bundle
    return <MainContent />;
}
""",
        correct_pattern="""
// Load analytics after hydration
function App() {
    useEffect(() => {
        import('@segment/analytics-next').then(({ default: Analytics }) => {
            Analytics.track('page_view');
        });
    }, []);
    return <MainContent />;
}
""",
    ),
    ReactRule(
        rule_id="bundle-conditional",
        category="Bundle Size Optimization",
        priority="CRITICAL",
        description="Use conditional imports for environment-specific code",
        incorrect_pattern="""
// Dev tools bundled in production
import { DevTools } from 'dev-tools';
import { Debugger } from 'react-debugger';

function App() {
    return (
        <>
            {process.env.NODE_ENV === 'development' && <DevTools />}
            <MainApp />
        </>
    );
}
""",
        correct_pattern="""
// Dev tools excluded from production bundle
const DevTools = process.env.NODE_ENV === 'development'
    ? lazy(() => import('dev-tools'))
    : () => null;

function App() {
    return (
        <>
            <Suspense fallback={null}>
                <DevTools />
            </Suspense>
            <MainApp />
        </>
    );
}
""",
    ),
    ReactRule(
        rule_id="bundle-preload",
        category="Bundle Size Optimization",
        priority="CRITICAL",
        description="Preload critical route chunks for faster navigation",
        incorrect_pattern="""
// Route chunks loaded on-demand, causing delay
function Navigation() {
    return (
        <nav>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/profile">Profile</Link>
        </nav>
    );
}

// Routes defined without preloading
const Dashboard = lazy(() => import('./Dashboard'));
const Profile = lazy(() => import('./Profile'));
""",
        correct_pattern="""
// Preload route chunks on link hover
const Dashboard = lazy(() => import('./Dashboard'));
const Profile = lazy(() => import('./Profile'));

function Navigation() {
    return (
        <nav>
            <Link
                to="/dashboard"
                onMouseEnter={() => import('./Dashboard')}
            >
                Dashboard
            </Link>
            <Link
                to="/profile"
                onMouseEnter={() => import('./Profile')}
            >
                Profile
            </Link>
        </nav>
    );
}
""",
    ),
    # Category 3: Server-Side Performance (HIGH)
    ReactRule(
        rule_id="server-auth-actions",
        category="Server-Side Performance",
        priority="HIGH",
        description="Validate authentication in server actions, not client components",
        incorrect_pattern="""
// Client-side auth check before server action
'use client';
function DeleteButton({ postId }: { postId: string }) {
    const session = useSession();

    const handleDelete = async () => {
        if (!session.user) return;  // Client-side check is bypassable
        await fetch('/api/posts/delete', {
            method: 'POST',
            body: JSON.stringify({ postId })
        });
    };
}
""",
        correct_pattern="""
// Server action validates auth
'use server';
async function deletePost(postId: string) {
    const session = await auth();
    if (!session?.user) throw new Error('Unauthorized');
    await db.post.delete({ where: { id: postId } });
}

// Client just calls the action
'use client';
function DeleteButton({ postId }: { postId: string }) {
    return <button onClick={() => deletePost(postId)}>Delete</button>;
}
""",
    ),
    ReactRule(
        rule_id="server-cache-react",
        category="Server-Side Performance",
        priority="HIGH",
        description="Use React cache() for deduplicating server-side fetches",
        incorrect_pattern="""
// Same data fetched multiple times in one request
async function UserProfile({ userId }: { userId: string }) {
    const user = await db.user.findUnique({ where: { id: userId } });
    return <div>{user.name}</div>;
}

async function UserAvatar({ userId }: { userId: string }) {
    const user = await db.user.findUnique({ where: { id: userId } });  // Duplicate query
    return <img src={user.avatar} />;
}
""",
        correct_pattern="""
// React cache deduplicates within a single request
import { cache } from 'react';

const getUser = cache(async (userId: string) => {
    return await db.user.findUnique({ where: { id: userId } });
});

async function UserProfile({ userId }: { userId: string }) {
    const user = await getUser(userId);
    return <div>{user.name}</div>;
}

async function UserAvatar({ userId }: { userId: string }) {
    const user = await getUser(userId);  // Returns cached result
    return <img src={user.avatar} />;
}
""",
    ),
    ReactRule(
        rule_id="server-cache-lru",
        category="Server-Side Performance",
        priority="HIGH",
        description="Use LRU cache for cross-request data persistence",
        incorrect_pattern="""
// Fetches same data on every request
async function getPopularPosts() {
    const posts = await db.post.findMany({
        orderBy: { views: 'desc' },
        take: 10
    });  // Re-queries database every time
    return posts;
}
""",
        correct_pattern="""
// LRU cache persists across requests
import { LRUCache } from 'lru-cache';

const cache = new LRUCache({ max: 500, ttl: 1000 * 60 * 5 });

async function getPopularPosts() {
    const cached = cache.get('popular-posts');
    if (cached) return cached;

    const posts = await db.post.findMany({
        orderBy: { views: 'desc' },
        take: 10
    });
    cache.set('popular-posts', posts);
    return posts;
}
""",
    ),
    ReactRule(
        rule_id="server-dedup-props",
        category="Server-Side Performance",
        priority="HIGH",
        description="Deduplicate server component props to avoid redundant fetches",
        incorrect_pattern="""
// Parent and child both fetch the same user
async function ProfilePage({ userId }: { userId: string }) {
    const user = await fetchUser(userId);
    return (
        <div>
            <h1>{user.name}</h1>
            <UserStats userId={userId} />  {/* Will fetch user again */}
        </div>
    );
}

async function UserStats({ userId }: { userId: string }) {
    const user = await fetchUser(userId);  // Duplicate fetch
    return <div>Posts: {user.postCount}</div>;
}
""",
        correct_pattern="""
// Parent passes data to child as prop
async function ProfilePage({ userId }: { userId: string }) {
    const user = await fetchUser(userId);
    return (
        <div>
            <h1>{user.name}</h1>
            <UserStats user={user} />  {/* Pass data, not ID */}
        </div>
    );
}

function UserStats({ user }: { user: User }) {
    return <div>Posts: {user.postCount}</div>;
}
""",
    ),
    ReactRule(
        rule_id="server-serialization",
        category="Server-Side Performance",
        priority="HIGH",
        description="Serialize server component props to avoid hydration mismatches",
        incorrect_pattern="""
// Date object causes hydration mismatch
async function PostMeta({ postId }: { postId: string }) {
    const post = await db.post.findUnique({ where: { id: postId } });
    return <ClientComponent date={post.createdAt} />;  // Date is not serializable
}

'use client';
function ClientComponent({ date }: { date: Date }) {
    return <time>{date.toLocaleDateString()}</time>;
}
""",
        correct_pattern="""
// Serialize Date to ISO string
async function PostMeta({ postId }: { postId: string }) {
    const post = await db.post.findUnique({ where: { id: postId } });
    return <ClientComponent date={post.createdAt.toISOString()} />;
}

'use client';
function ClientComponent({ date }: { date: string }) {
    return <time>{new Date(date).toLocaleDateString()}</time>;
}
""",
    ),
    ReactRule(
        rule_id="server-parallel-fetching",
        category="Server-Side Performance",
        priority="HIGH",
        description="Fetch data at the layout level to parallelize with page data",
        incorrect_pattern="""
// Layout and page fetch sequentially
async function Layout() {
    const nav = await fetchNavigation();  // Blocks page
    return <nav>{nav}</nav>;
}

async function Page() {
    const content = await fetchContent();  // Waits for layout
    return <main>{content}</main>;
}
""",
        correct_pattern="""
// Layout and page fetch in parallel
async function Layout() {
    const navPromise = fetchNavigation();  // Start fetch
    return (
        <Suspense fallback={<NavSkeleton />}>
            <Navigation promise={navPromise} />
        </Suspense>
    );
}

async function Page() {
    const content = await fetchContent();  // Fetches in parallel with nav
    return <main>{content}</main>;
}
""",
    ),
    ReactRule(
        rule_id="server-after-nonblocking",
        category="Server-Side Performance",
        priority="HIGH",
        description="Use unstable_after for non-blocking post-response work",
        incorrect_pattern="""
// Analytics blocks response
'use server';
async function submitForm(formData: FormData) {
    await db.form.create({ data: formData });
    await analytics.track('form_submitted');  // Blocks response
    await sendEmail(formData.email);          // Blocks response
    return { success: true };
}
""",
        correct_pattern="""
// Analytics runs after response sent
import { unstable_after as after } from 'next/server';

'use server';
async function submitForm(formData: FormData) {
    await db.form.create({ data: formData });

    after(() => {
        analytics.track('form_submitted');  // Non-blocking
        sendEmail(formData.email);           // Non-blocking
    });

    return { success: true };  // Response sent immediately
}
""",
    ),
]

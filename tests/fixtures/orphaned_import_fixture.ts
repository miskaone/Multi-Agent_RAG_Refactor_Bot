import { useState, useCallback } from 'react';

export function Counter() {
    const [count, setCount] = useState(0);
    return count;
}

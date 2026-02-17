import { fetchUserById } from './callee';

export function loadProfile() {
    const user = fetchUserById('123', { expand: true });
    return user;
}

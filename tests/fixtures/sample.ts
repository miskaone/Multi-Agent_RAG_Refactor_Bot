import { debounce } from './utils';

class UserService {
  async getUser(id: string): Promise<User> {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
  }
}

function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

interface User {
  id: string;
  name: string;
  email: string;
}

export { UserService, validateEmail };

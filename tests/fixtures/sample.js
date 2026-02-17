import { slugify } from './utils';

function calculateTotal(items) {
  return items.reduce((sum, item) => sum + item.price, 0);
}

const formatPrice = (amount) => {
  return `$${amount.toFixed(2)}`;
};

export { calculateTotal, formatPrice };

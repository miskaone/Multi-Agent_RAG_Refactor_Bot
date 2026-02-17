import React, { Suspense } from 'react';
import { slugify } from './utils';

async function ProductList() {
  const products = await fetch('https://api.example.com/products').then(r => r.json());

  return (
    <div className="product-list">
      <h1>Our Products</h1>
      <Suspense fallback={<div>Loading products...</div>}>
        <ProductGrid products={products} />
      </Suspense>
    </div>
  );
}

async function ProductGrid({ products }) {
  return (
    <div className="grid">
      {products.map(product => (
        <div key={product.id}>{product.name}</div>
      ))}
    </div>
  );
}

export default ProductList;

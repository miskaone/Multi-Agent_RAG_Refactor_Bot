"use client"
import React, { useState, useEffect } from 'react';
import { slugify } from './utils';

function ProductCard({ product }) {
  const [quantity, setQuantity] = useState(0);

  useEffect(() => {
    console.log(`Product ${product.name} quantity changed: ${quantity}`);
  }, [quantity, product.name]);

  return (
    <div className="product-card">
      <h2>{product.name}</h2>
      <p>${product.price}</p>
      <button onClick={() => setQuantity(quantity + 1)}>
        Add to Cart
      </button>
      <span>Quantity: {quantity}</span>
    </div>
  );
}

export default ProductCard;

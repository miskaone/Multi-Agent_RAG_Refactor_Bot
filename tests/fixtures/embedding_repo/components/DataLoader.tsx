"use client";

import React, { useState, useEffect } from 'react';

interface DataLoaderProps {
  url: string;
  children: (data: any) => React.ReactNode;
}

export function DataLoader({ url, children }: DataLoaderProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(url)
      .then(res => res.json())
      .then(json => {
        setData(json);
        setLoading(false);
      });
  }, [url]);

  if (loading) return <div>Loading...</div>;
  return <>{children(data)}</>;
}

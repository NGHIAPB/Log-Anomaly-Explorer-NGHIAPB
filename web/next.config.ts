import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // cacheComponents/partialPrefetching (mac dinh cua scaffold) nham toi cac
  // trang co the cache/ISR tung phan - khong phu hop voi dashboard van hanh
  // nay (du lieu log/cluster luon phai la du lieu song), nen tat de tranh
  // phai boc Suspense cho moi cho doc searchParams/fetch dong.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

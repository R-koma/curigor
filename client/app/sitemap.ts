import type { MetadataRoute } from "next";

import { OPERATOR } from "@/lib/legal";

const baseUrl =
  process.env.NEXT_PUBLIC_BETTER_AUTH_URL || "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: baseUrl, priority: 1 },
    { url: `${baseUrl}/sign-in`, priority: 0.5 },
    { url: `${baseUrl}/sign-up`, priority: 0.8 },
    ...(OPERATOR !== null
      ? [
          { url: `${baseUrl}/terms`, priority: 0.3 },
          { url: `${baseUrl}/privacy`, priority: 0.3 },
        ]
      : []),
  ];
}

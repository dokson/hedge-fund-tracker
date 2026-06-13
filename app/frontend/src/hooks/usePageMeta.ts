import { useEffect } from "react";

interface PageMeta {
  title: string;
  description: string;
  /** Absolute canonical URL for this route. */
  canonical: string;
  /** Structured-data objects injected as application/ld+json. */
  jsonLd?: object[];
}

/** Upserts a <meta> tag and returns a function that restores the prior state. */
function upsertMeta(attr: "name" | "property", key: string, content: string): () => void {
  const selector = `meta[${attr}="${key}"]`;
  const existing = document.head.querySelector<HTMLMetaElement>(selector);
  if (existing) {
    const prev = existing.getAttribute("content");
    existing.setAttribute("content", content);
    return () => {
      if (prev === null) existing.removeAttribute("content");
      else existing.setAttribute("content", prev);
    };
  }
  const el = document.createElement("meta");
  el.setAttribute(attr, key);
  el.setAttribute("content", content);
  document.head.appendChild(el);
  return () => el.remove();
}

/** Upserts <link rel="canonical"> and returns a restore function. */
function upsertCanonical(href: string): () => void {
  const existing = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (existing) {
    const prev = existing.getAttribute("href");
    existing.setAttribute("href", href);
    return () => {
      if (prev === null) existing.removeAttribute("href");
      else existing.setAttribute("href", prev);
    };
  }
  const el = document.createElement("link");
  el.setAttribute("rel", "canonical");
  el.setAttribute("href", href);
  document.head.appendChild(el);
  return () => el.remove();
}

/**
 * Manages per-route document head metadata (title, description, canonical, Open
 * Graph tags) and JSON-LD for the live SPA, restoring the previous values when
 * the route unmounts. The deployed crawler-facing copy is baked into static
 * HTML at build time; this keeps the in-app navigation experience tagged too.
 */
export function usePageMeta({ title, description, canonical, jsonLd }: PageMeta): void {
  const serializedJsonLd = JSON.stringify(jsonLd ?? []);

  useEffect(() => {
    const prevTitle = document.title;
    document.title = title;

    const restorers = [
      upsertMeta("name", "description", description),
      upsertCanonical(canonical),
      upsertMeta("property", "og:title", title),
      upsertMeta("property", "og:description", description),
      upsertMeta("property", "og:url", canonical),
    ];

    const scripts = (JSON.parse(serializedJsonLd) as object[]).map((ld) => {
      const el = document.createElement("script");
      el.type = "application/ld+json";
      el.text = JSON.stringify(ld);
      el.dataset.managed = "page-meta";
      document.head.appendChild(el);
      return el;
    });

    return () => {
      document.title = prevTitle;
      restorers.forEach((restore) => restore());
      scripts.forEach((el) => el.remove());
    };
  }, [title, description, canonical, serializedJsonLd]);
}

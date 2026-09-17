import { useEffect } from 'react';

interface PageMetaProps {
  title: string;
  path: '/' | '/plans' | '/404';
}

export function PageMeta({ title, path }: PageMetaProps) {
  useEffect(() => {
    document.title = title;
    const canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (canonical) canonical.href = new URL(path, 'https://veridexeai.com').href;
  }, [path, title]);

  return null;
}

import { UrlCrawlerPage } from '@/testCase Frontend';

export const metadata = {
  title: 'URL Crawler – Generate Test Scripts',
  description: 'Crawl any deployed URL and automatically generate Playwright test scripts for every discovered page.',
};

export default function Page() {
  return <UrlCrawlerPage />;
}

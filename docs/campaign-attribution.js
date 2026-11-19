/* Carry reviewed campaign labels through the portfolio. No cookies, storage or requests. */
(() => {
  'use strict';

  const keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
  // Values are campaign vocabulary, never arbitrary visitor names, emails or search text.
  const sources = new Set([
    'github', 'wordpress', 'linkedin', 'reddit', 'facebook', 'instagram', 'threads',
    'x', 'twitter', 'bluesky', 'mastodon', 'youtube', 'tiktok', 'pinterest',
    'contra', 'freelancer', 'upwork', 'fiverr', 'guru', 'useme',
    'comeup', 'workana', 'truelancer', 'malt', 'braintrust', 'arc', 'toptal',
    'peerlist', 'devto', 'hashnode', 'medium', 'substack', 'hackernews',
    'google', 'bing', 'duckduckgo', 'baidu', 'yandex', 'naver', 'yahoo',
    'wechat', 'weibo', 'zhihu', 'xiaohongshu', 'bilibili', 'douyin',
    'vk', 'telegram', 'dzen', 'line', 'kakao', 'zalo', 'discord', 'slack',
    'newsletter', 'partner', 'referral', 'direct'
  ]);
  const media = new Set([
    'portfolio', 'social', 'organic', 'organic_social', 'referral', 'community', 'marketplace',
    'profile', 'article', 'video', 'email', 'partner', 'directory'
  ]);
  const content = new Set([
    'api', 'cicd', 'ai', 'web', 'saas', 'realtime', 'security', 'observability',
    'finops', 'data', 'rag', 'integration', 'diagnostic', 'demo', 'guide',
    'checklist', 'profile', 'service-listing', 'hero', 'contact',
    'api-diagnostic', 'cicd-diagnostic', 'ai-diagnostic', 'order_retry_checklist', 'order_retry'
  ]);
  const terms = new Set([
    'java', 'spring-boot', 'api-integration', 'kafka', 'ci-cd', 'devops',
    'kubernetes', 'ai-evaluation', 'rag', 'web-development', 'automation'
  ]);

  function allowed(key, value) {
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(value)) return false;
    if (key === 'utm_source') return sources.has(value);
    if (key === 'utm_medium') return media.has(value);
    if (key === 'utm_campaign') {
      return /^(it_services|api_diagnostic|cicd_diagnostic|ai_diagnostic)_20\d{2}(0[1-9]|1[0-2])$/.test(value);
    }
    if (key === 'utm_content') return content.has(value) || /^post-(0[1-9]|[12]\d|3[01])$/.test(value);
    return terms.has(value);
  }

  function campaign(search) {
    const query = new URLSearchParams(search);
    const labels = new Map();
    for (const key of keys) {
      const values = query.getAll(key);
      // Reject the whole ambiguous/invalid bundle, retaining the authored fallback links.
      if (values.length > 1 || (values.length === 1 && !allowed(key, values[0]))) return null;
      if (values.length === 1) labels.set(key, values[0]);
    }
    return labels.has('utm_source') ? labels : null;
  }

  const current = new URL(window.location.href);
  const labels = campaign(current.search);
  if (!labels) return;

  const pages = new Set([
    '', 'index.html', 'api-integration-diagnostic.html',
    'cicd-pipeline-diagnostic.html', 'ai-regression-diagnostic.html',
    'services-en.html', 'services-ro.html', 'services-es.html', 'services-pt.html', 'services-fr.html', 'services-zh-hans.html'
  ].map(path => new URL(path, new URL('.', current)).pathname));

  for (const anchor of document.querySelectorAll('a[href]')) {
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#')) continue;
    let target;
    try { target = new URL(href, current); } catch { continue; }
    if (target.username || target.password) continue;
    const internal = target.origin === current.origin && pages.has(target.pathname)
      && ['https:', 'http:'].includes(target.protocol);
    const enquiry = target.origin === 'https://stefanescumircea1990.wordpress.com'
      && target.pathname === '/software-services/' && target.hash === '#project-enquiry';
    if (!internal && !enquiry) continue;
    // Only these validated labels move forward. Unknown input parameters are not copied.
    for (const [key, value] of labels) target.searchParams.set(key, value);
    anchor.setAttribute('href', target.href);
    // Do not expose any incoming query values through a navigation Referer header.
    anchor.setAttribute('referrerpolicy', 'origin');
  }
})();

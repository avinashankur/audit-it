'use client';

import { useEffect, useId, useState } from 'react';
import { useTheme } from 'next-themes';

interface MermaidProps {
  chart: string;
}

export function Mermaid({ chart }: MermaidProps) {
  const { resolvedTheme } = useTheme();
  const rawId = useId();
  const id = 'mermaid-' + rawId.replace(/[^a-zA-Z0-9_-]/g, '');
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function renderChart() {
      try {
        const { default: mermaid } = await import('mermaid');

        const isDark = resolvedTheme === 'dark';
        const neutralBorder = isDark ? '#52525b' : '#71717a';
        const neutralLine = isDark ? '#71717a' : '#71717a';

        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          fontFamily: 'inherit',
          fontSize: 13,
          themeCSS: 'margin: 0 !important;',
          theme: 'base',
          look: 'classic',
          flowchart: {
            padding: 8,
          },
          themeVariables: {
            useGradient: false,
            dropShadow: 'none',
            darkMode: isDark,
            background: 'transparent',
            fontSize: '13px',
            primaryColor: isDark ? '#18181b' : '#ffffff',
            primaryTextColor: isDark ? '#f4f4f5' : '#18181b',
            primaryBorderColor: neutralBorder,
            secondaryColor: isDark ? '#27272a' : '#f4f4f5',
            secondaryTextColor: isDark ? '#f4f4f5' : '#18181b',
            secondaryBorderColor: neutralBorder,
            tertiaryColor: isDark ? '#18181b' : '#ffffff',
            tertiaryBorderColor: neutralBorder,
            lineColor: neutralLine,
            arrowheadColor: neutralLine,
            nodeBorder: neutralBorder,
            textColor: isDark ? '#f4f4f5' : '#18181b',
            clusterBkg: isDark ? '#121214' : '#fafafa',
            clusterBorder: isDark ? '#27272a' : '#e4e4e7',
          },
        });

        const cleanChart = chart.trim();
        const { svg: renderedSvg } = await mermaid.render(id, cleanChart);

        if (isMounted) {
          setSvg(renderedSvg);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    }

    renderChart();

    return () => {
      isMounted = false;
    };
  }, [chart, resolvedTheme, id]);

  if (error) {
    return (
      <div className="my-4 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-xs text-red-500 font-mono">
        Failed to render diagram: {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-4 flex h-24 items-center justify-center rounded-lg border border-fd-border bg-fd-card/30 text-xs text-fd-muted-foreground animate-pulse">
        Rendering diagram...
      </div>
    );
  }

  return (
    <div
      className="mermaid-wrapper my-4 flex w-full justify-start overflow-x-auto rounded-lg border border-fd-border bg-fd-card/30 p-4 shadow-xs [&>svg]:m-0! [&>svg]:max-w-135 [&>svg]:w-auto [&>svg]:h-auto [&_rect]:filter-none! [&_polygon]:filter-none! [&_circle]:filter-none! [&_.node_rect]:stroke-[1.25px]!"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

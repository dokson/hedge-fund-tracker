import React, { useEffect, useRef, memo } from 'react';
import { useTheme } from 'next-themes';

interface TradingViewDeltaWidgetProps {
  symbolTicker: string;
  height?: string;
}

function TradingViewWidget({ symbolTicker, height = '400px' }: TradingViewDeltaWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    const config = {
      autosize: true,
      symbol: symbolTicker,
      interval: 'D',
      timezone: 'America/New_York',
      theme: theme === 'dark' ? 'dark' : 'light',
      style: '1',
      locale: 'en',
      enable_publishing: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      calendar: false,
      hide_volume: false,
      support_host: 'https://www.tradingview.com',
      width: '100%',
      height: '100%',
      container_id: 'tradingview-delta-widget',
      dateRanges: [
        '1d|1',
        '1m|30',
        '3m|60',
        '12m|1D',
        '60m|1W',
        'all|1M'
      ],
      range: '3m',
      defaultDateRange: '3m',
    };

    container.current.innerHTML = '';
    container.current.id = 'tradingview-delta-widget';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify(config);

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
        delete (container.current as any).id;
      }
    };
  }, [symbolTicker, theme]);

  return (
    <div className="tradingview-widget-container" ref={container} style={{ height }}>
      <div className="tradingview-widget-container__widget"></div>
      <div className="tradingview-widget-copyright">
        <a href={`https://www.tradingview.com/symbols/${symbolTicker}/`} rel="noopener nofollow" target="_blank">
          <span className="blue-text">{symbolTicker} stock price</span>
        </a>
        <span className="trademark">&nbsp;by TradingView</span>
      </div>
    </div>
  );
}

export default memo(TradingViewWidget);

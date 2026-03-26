import React, { useEffect, useRef, memo, useState } from 'react';
import { useTheme } from 'next-themes';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface TradingViewWidgetProps {
  symbolTicker: string;
  height?: string;
}

interface WidgetConfig {
  autosize?: boolean;
  symbol: string;
  interval?: string;
  timezone?: string;
  theme?: string;
  style?: string;
  locale?: string;
  enable_publishing?: boolean;
  hide_top_toolbar?: boolean;
  hide_legend?: boolean;
  save_image?: boolean;
  calendar?: boolean;
  hide_volume?: boolean;
  support_host?: string;
  width?: string;
  height?: string;
  dateRanges?: string[];
  range?: string;
  colorTheme?: string;
  displayMode?: string;
  isTransparent?: boolean;
}

function TradingViewWidget({ symbolTicker, height = '400px' }: TradingViewWidgetProps) {
  const [activeTab, setActiveTab] = useState('chart');
  const { theme } = useTheme();
  const widgetTheme = theme === 'dark' ? 'dark' : 'light';

  const ChartWidget = ({ symbol, theme }: { symbol: string; theme: string }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!containerRef.current) return;

      const config: WidgetConfig = {
        autosize: true,
        symbol: symbol,
        interval: 'D',
        timezone: 'America/New_York',
        theme: theme,
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
        dateRanges: [
          '1d|1',
          '1m|30',
          '3m|60',
          '12m|1D',
          '60m|1W',
          'all|1M'
        ],
        range: '3m',
      };

      containerRef.current.innerHTML = '';
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
      script.type = 'text/javascript';
      script.async = true;
      script.innerHTML = JSON.stringify(config);
      containerRef.current.appendChild(script);
    }, [symbol, theme]);

    return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
  };

  const FinancialsWidget = ({ symbol, theme }: { symbol: string; theme: string }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!containerRef.current) return;

      const config: WidgetConfig = {
        symbol: symbol,
        colorTheme: theme,
        displayMode: 'regular',
        isTransparent: false,
        locale: 'en',
        width: '100%',
        height: '100%',
      };

      containerRef.current.innerHTML = '';
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-financials.js';
      script.type = 'text/javascript';
      script.async = true;
      script.innerHTML = JSON.stringify(config);
      containerRef.current.appendChild(script);
    }, [symbol, theme]);

    return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
  };

  const ProfileWidget = ({ symbol, theme }: { symbol: string; theme: string }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!containerRef.current) return;

      const config: WidgetConfig = {
        symbol: symbol,
        colorTheme: theme,
        isTransparent: false,
        locale: 'en',
        width: '100%',
        height: '100%',
      };

      containerRef.current.innerHTML = '';
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-profile.js';
      script.type = 'text/javascript';
      script.async = true;
      script.innerHTML = JSON.stringify(config);
      containerRef.current.appendChild(script);
    }, [symbol, theme]);

    return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
  };

  return (
    <div className="tradingview-widget-container" style={{ height }}>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full h-full flex flex-col">
        <TabsList className="w-full justify-start border-b rounded-none bg-card h-10 px-0 pb-0 shrink-0">
          <TabsTrigger value="chart" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground rounded-none px-4 text-muted-foreground">
            Chart
          </TabsTrigger>
          <TabsTrigger value="fundamental" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground rounded-none px-4 text-muted-foreground">
            Fundamental Data
          </TabsTrigger>
          <TabsTrigger value="profile" className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-foreground rounded-none px-4 text-muted-foreground">
            Company Profile
          </TabsTrigger>
        </TabsList>
        <div className="flex-1 min-h-0 overflow-hidden">
          <TabsContent value="chart" className="mt-0 h-full p-0">
            <ChartWidget symbol={symbolTicker} theme={widgetTheme} />
          </TabsContent>
          <TabsContent value="fundamental" className="mt-0 h-full p-0">
            <FinancialsWidget symbol={symbolTicker} theme={widgetTheme} />
          </TabsContent>
          <TabsContent value="profile" className="mt-0 h-full p-0">
            <ProfileWidget symbol={symbolTicker} theme={widgetTheme} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export default memo(TradingViewWidget);

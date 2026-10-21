import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  ChartData,
  ChartOptions,
  ChartType,
} from 'chart.js';
import { Bar, Line, Pie, Doughnut, Scatter } from 'react-chartjs-2';

// Quadrants plugin for Chart.js, based on the example
const quadrantsPlugin = {
  id: 'quadrants',
  beforeDraw(chart, args, options) {
    try {
      // Check if quadrants options are defined - only apply when they are present
      if (!options || !options.topLeft || !options.topRight ||
          !options.bottomLeft || !options.bottomRight) {
        return; // Skip this plugin if quadrant colors aren't defined
      }

      if (!chart || !chart.scales || !chart.scales.x || !chart.scales.y) {
        return; // Exit early if requirements not met
      }

      const {ctx, chartArea, scales} = chart;
      if (!chartArea || !scales) return;

      const {left, top, right, bottom} = chartArea;
      const {x, y} = scales;

      // Calculate the middle points based on options or scale range
      // Options can specify fixed values (e.g., midX: 5 for CSAT scale)
      // Otherwise, use the midpoint of the scale range
      let midXValue, midYValue;

      if (options.midX !== undefined) {
        midXValue = options.midX;
      } else {
        midXValue = (x.min + x.max) / 2;
      }

      if (options.midY !== undefined) {
        midYValue = options.midY;
      } else {
        midYValue = (y.min + y.max) / 2;
      }

      const midX = x.getPixelForValue(midXValue);
      const midY = y.getPixelForValue(midYValue);

      ctx.save();

      // Apply the quadrant colors directly from options
      // Top Left (Yellow - High Value, Low Satisfaction)
      ctx.fillStyle = options.topLeft;
      ctx.fillRect(left, top, midX - left, midY - top);

      // Top Right (Green - High Value, High Satisfaction)
      ctx.fillStyle = options.topRight;
      ctx.fillRect(midX, top, right - midX, midY - top);

      // Bottom Right (Blue - Low Value, High Satisfaction)
      ctx.fillStyle = options.bottomRight;
      ctx.fillRect(midX, midY, right - midX, bottom - midY);

      // Bottom Left (Red - Low Value, Low Satisfaction)
      ctx.fillStyle = options.bottomLeft;
      ctx.fillRect(left, midY, midX - left, bottom - midY);

      ctx.restore();
    } catch (e) {
      console.error('Error drawing quadrants:', e);
    }
  }
};

// Point labels plugin - draws text labels below point images
const pointLabelsPlugin = {
  id: 'pointLabels',
  afterDatasetsDraw(chart, args, options) {
    try {
      if (!options || !options.labels || !options.hasImages) {
        return;
      }

      const {ctx, scales} = chart;
      const {x, y} = scales;
      const dataset = chart.data.datasets[0];

      ctx.save();
      ctx.font = '9px sans-serif';
      ctx.fillStyle = '#666';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      dataset.data.forEach((point, index) => {
        const xPos = x.getPixelForValue(point.x);
        const yPos = y.getPixelForValue(point.y);
        const label = options.labels[index];

        if (label) {
          // Draw label below the point (20px below for image radius + spacing)
          ctx.fillText(label.toUpperCase(), xPos, yPos + 25);
        }
      });

      ctx.restore();
    } catch (e) {
      console.error('Error drawing point labels:', e);
    }
  }
};

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  quadrantsPlugin,
  pointLabelsPlugin
);

export interface ChartWidgetProps {
  title: string;
  data: {
    type: 'bar' | 'line' | 'pie' | 'doughnut' | 'scatter';
    chartData: ChartData<'bar' | 'line' | 'pie' | 'doughnut' | 'scatter'>;
    options?: ChartOptions<'bar' | 'line' | 'pie' | 'doughnut' | 'scatter'>;
    urls?: {[key: string]: string}[];  // URLs for each data point in each dataset
  };
  width?: number;
  containerClassName?: string;
}

type SupportedChartType = Extract<ChartType, 'bar' | 'line' | 'pie' | 'doughnut' | 'scatter'>;
type QuadrantOptions = {
  topLeft?: string;
  topRight?: string;
  bottomLeft?: string;
  bottomRight?: string;
  midX?: number;
  midY?: number;
};
type SupportedChartOptions = ChartOptions<SupportedChartType> & {
  plugins?: NonNullable<ChartOptions<SupportedChartType>['plugins']> & {
    quadrants?: QuadrantOptions;
  };
};

const ChartWidget = ({ title, data, width, containerClassName }: ChartWidgetProps) => {
  // Log props for debugging
  console.log('ChartWidget.web props:', { title, data, width, containerClassName });
  // Default options
  const defaultOptions: ChartOptions<'bar' | 'line' | 'pie' | 'doughnut' | 'scatter'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: false,
      },
    },
    onClick: (event, elements, chart) => {
      if (elements.length === 0 || !data.urls) return;
      
      const clickedElement = elements[0];
      const { datasetIndex, index } = clickedElement;
      
      // Check if we have a URL for this specific point
      if (data.urls[datasetIndex] && data.urls[datasetIndex][index]) {
        const url = data.urls[datasetIndex][index];
        if (url) {
          if (/^https?:\/\//.test(url)) {
            window.open(url, '_blank', 'noopener,noreferrer');
          } else {
            window.location.assign(url);
          }
        }
      }
    },
  };

  // Combine default options with provided options
  const chartOptions: SupportedChartOptions = {
    ...defaultOptions,
    ...data.options,
  };

  // Fix for empty quadrant charts: set a fake Y-axis max if there's no data
  if (chartOptions.plugins?.quadrants && chartOptions.scales?.y) {
    const yMax = chartOptions.scales.y.max;
    // If Y-axis max is 0 or undefined, set a default value so quadrants display
    if (!yMax || yMax === 0) {
      chartOptions.scales.y.max = 100000; // Default max for empty chart
      // Also update midY if it was calculated from the zero max
      if (chartOptions.plugins.quadrants.midY === 0 || !chartOptions.plugins.quadrants.midY) {
        chartOptions.plugins.quadrants.midY = 50000; // Half of 100k (centered quadrant)
      }
    }
  }

  if (!data || !data.chartData) {
    return (
      <div className={`h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col ${containerClassName || ''}`} data-width={width}>
        <div className="p-3 border-b border-border-1 bg-bg-2">
          <h3 className="text-sm font-semibold text-fg-1">{title || 'Chart'}</h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-4 text-fg-3 text-sm">
          No chart data available
        </div>
      </div>
    );
  }

  return (
    <div className="h-[350px] w-full rounded-lg bg-bg-1 border border-border-1 flex flex-col">
      <div className="p-3 border-b border-border-1 bg-bg-2">
        <h3 className="text-sm font-semibold text-fg-1">{title || 'Chart'}</h3>
      </div>
      <div className="flex-1 p-4">
        {data.type === 'bar' ? (
          <Bar data={data.chartData as ChartData<'bar'>} options={chartOptions as ChartOptions<'bar'>} />
        ) : data.type === 'line' ? (
          <Line data={data.chartData as ChartData<'line'>} options={chartOptions as ChartOptions<'line'>} />
        ) : data.type === 'pie' ? (
          <Pie data={data.chartData as ChartData<'pie'>} options={chartOptions as ChartOptions<'pie'>} />
        ) : data.type === 'doughnut' ? (
          <Doughnut
            data={data.chartData as ChartData<'doughnut'>}
            options={chartOptions as ChartOptions<'doughnut'>}
          />
        ) : data.type === 'scatter' ? (
          <Scatter
            data={data.chartData as ChartData<'scatter'>}
            options={chartOptions as ChartOptions<'scatter'>}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-danger text-sm">
            Unsupported chart type: {data.type}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChartWidget;

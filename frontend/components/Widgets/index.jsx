import MetabaseEmbeddedQuestionWidget from './MetabaseEmbeddedQuestionWidget';
import ChartWidget from './ChartWidget';
import ListWidget from './ListWidget';

// Export all widget components
export {
  MetabaseEmbeddedQuestionWidget,
  ChartWidget,
  ListWidget,
};

// Widget registry for dynamic widget loading
const WIDGET_REGISTRY = {
  MetabaseEmbeddedQuestionWidget,
  ChartWidget,
  ListWidget,
};

/**
 * Renders the appropriate widget component based on type
 * @param {Object} props - Widget props
 * @param {string} props.type - Widget type
 * @param {Object} props.data - Widget data
 * @param {string} props.title - Widget title
 * @param {number} props.width - Widget width (1-3)
 * @param {string} props.containerClassName - Additional class name for the container
 */
export const WidgetRenderer = ({ type, data, title, width, containerClassName }) => {
  const WidgetComponent = WIDGET_REGISTRY[type];
  
  if (!WidgetComponent) {
    console.warn(`Widget type "${type}" not found in registry`);
    return null;
  }
  
  return <WidgetComponent 
    data={data} 
    title={title} 
    width={width} 
    containerClassName={containerClassName} 
  />;
};

export default WIDGET_REGISTRY;
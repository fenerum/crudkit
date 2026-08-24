import ReadOnlyField from "./ReadOnlyField";

// Import specific field components
import CharField from "./Fields/CharField";
import TextField from "./Fields/TextField";
import DateField from "./Fields/DateField";
import DateTimeField from "./Fields/DateTimeField";
import DecimalField from "./Fields/DecimalField";
import ForeignKeyField from "./Fields/ForeignKeyField";
import ChoiceField from "./Fields/ChoiceField";
import ImageField from "./Fields/ImageField";
import WYSIWYGEditorField from "./Fields/WYSIWYGEditorField";
import EmailWYSIWYGEditorField from "./Fields/EmailWYSIWYGEditorField";
import Checkbox from "./Fields/Checkbox";
import JSONField from "./Fields/JSONField";
import FieldsEditor from "./Fields/FieldsEditor";
import LayoutFieldsEditor from "./Fields/LayoutFieldsEditor";
import InlinesEditor from "./Fields/InlinesEditor";
import MoneyField from "./Fields/MoneyField";

/**
 * A component that renders an appropriate field component based on the field type
 * and metadata. If form mode is disabled or the field is not editable,
 * it renders a read-only view instead.
 * 
 * For editable fields, it expects to be used within a FormProvider context.
 */
export default function GenericDetailField({ fieldName, value, form, metadata, modelType }) {
  // Read-only fields don't need form control
  if (!form || !metadata.editable || metadata.auto_created) {
    return (
      <ReadOnlyField
        value={value}
        metadata={metadata}
      />
    );
  }
  
  // Common props to pass to all field components
  // For existing values, always use the field value (even if null)
  // Only use metadata.default as fallback when value is undefined (new objects)
  // This prevents silently using defaults when editing objects with null values
  const fieldProps = {
    fieldName,
    defaultValue: value !== undefined ? value : metadata.default,
    metadata,
  };

  // Layouts get the multi-row editor (rows of fields + drag to reorder rows
  // + ability to put multiple fields side-by-side). Views only support a flat
  // ordered list, so they keep the simpler editor.
  if (fieldName === "fields" && modelType === "LAY") {
    return <LayoutFieldsEditor {...fieldProps} />;
  }
  if (fieldName === "fields" && modelType === "VIW") {
    return <FieldsEditor {...fieldProps} />;
  }

  // Smart editor for Layout's `inlines` — a list of (related model, fields)
  // tuples. Each row gets its own field picker for its model.
  if (fieldName === "inlines" && modelType === "LAY") {
    return <InlinesEditor {...fieldProps} />;
  }

  // Select appropriate field component based on type or other metadata properties
  if (metadata.choices) {
    return <ChoiceField {...fieldProps} />;
  }

  switch (metadata.type) {
    case "TextField":
      return <TextField {...fieldProps} />;
    case "JSONField":
      return <JSONField {...fieldProps} />;
    case "ForeignKey":
    case "OneToOneField":
      return <ForeignKeyField {...fieldProps} />;
    case "ImageField":
      return <ImageField {...fieldProps} />;
    case "WYSIWYGEditorField":
      return <WYSIWYGEditorField {...fieldProps} modelType={modelType} />;
    case "EmailWYSIWYGEditorField":
      return <EmailWYSIWYGEditorField {...fieldProps} modelType={modelType} />;
    case "BooleanField":
      return <Checkbox {...fieldProps} />;
    case "CharField":
      return <CharField {...fieldProps} />;
    case "DateField":
      return <DateField {...fieldProps} />;
    case "DateTimeField":
      return <DateTimeField {...fieldProps} />;
    case "DecimalField":
      return <DecimalField {...fieldProps} />;
    case "MoneyField":
      return <MoneyField {...fieldProps} />;
    default:
      // Fallback for any other field types
      return <CharField {...fieldProps} />;
  }
}
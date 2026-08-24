import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { url } from "../utils/urls";
import ReadOnlyField from "./ReadOnlyField.jsx";
import moment from "moment-timezone";
import { Link } from "react-router-dom";
import { Icon, PriorityBars } from "./ui";
import {
  AMOUNT_FIELDS, PRIORITY_FIELDS,
  findFieldByNames, priorityLevel,
} from "../utils/cardFields";

export default function KanbanItem({ id, object, fieldList, metadata }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id });

  if (!object) return null;

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const priorityField = findFieldByNames(object, PRIORITY_FIELDS);
  const prioLevel = priorityLevel(priorityField ? object[priorityField] : null);

  const amountField = findFieldByNames(object, AMOUNT_FIELDS);
  const amountValue = amountField ? object[amountField] : null;
  const amountMeta = amountField ? metadata.fields[amountField] : null;

  const updatedAt = object.updated_at ? moment(object.updated_at) : null;
  const isStale = updatedAt && moment().diff(updatedAt, 'days') > 7;

  const titleField = fieldList[0];
  const skipFields = new Set([priorityField, amountField].filter(Boolean));
  const subFields = fieldList.slice(1).filter(f => !skipFields.has(f));

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="ck-deal-card"
    >
      <Link to={url(object.id)} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="ck-dc-head">
          <span className="ck-dc-id">{object.id}</span>
          {prioLevel != null && <PriorityBars level={prioLevel} />}
        </div>

        {titleField && (
          <div className="ck-dc-title truncate">
            <ReadOnlyField value={object[titleField]} metadata={metadata.fields[titleField]} link={false} />
          </div>
        )}

        {subFields.length > 0 && (
          <div className="ck-dc-tags">
            {subFields.map((field) => (
              <span key={field} className="ck-tag">
                <ReadOnlyField value={object[field]} metadata={metadata.fields[field]} link={false} />
              </span>
            ))}
          </div>
        )}

        <div className="ck-dc-foot">
          {amountValue != null && amountMeta && (
            <span className="ck-dc-amt">
              <ReadOnlyField value={amountValue} metadata={amountMeta} link={false} />
            </span>
          )}
          {updatedAt && (
            <span
              className="ck-dc-meta"
              style={isStale ? { color: 'var(--warn)' } : undefined}
            >
              <Icon name="clock" size={11} color="currentColor" />
              {updatedAt.fromNow(true)}
            </span>
          )}
          <span className="ck-dc-spacer" />
          {object.object_images && object.object_images.length > 0 && (
            <div className="flex items-center">
              {object.object_images.slice(0, 3).map((src, i) => (
                <img
                  key={i}
                  src={src}
                  alt=""
                  className="rounded-full"
                  style={{
                    width: 18,
                    height: 18,
                    objectFit: 'cover',
                    border: '1px solid var(--bg-2)',
                    marginLeft: i === 0 ? 0 : -6,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </Link>
    </div>
  );
}

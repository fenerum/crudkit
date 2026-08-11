import { useParams } from 'react-router-dom';
import List from './list';
import Detail from './detail';
import NotFound from './not-found';

const LIST_RE = /^[A-Z]{3}$/;
const DETAIL_RE = /^[A-Z]{3}\d+$/;

export default function SegmentIndex() {
  const { segment } = useParams();
  const value = String(segment || '');

  if (LIST_RE.test(value)) return <List />;
  if (DETAIL_RE.test(value)) return <Detail />;
  return <NotFound />;
}

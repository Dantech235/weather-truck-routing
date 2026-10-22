import { useParams } from 'react-router-dom';
import { usePlan } from '../api/queries';
import { PlannerLayout } from './PlannerLayout';

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = usePlan(id);
  return <PlannerLayout plan={data ?? null} loading={isLoading} loadError={error ?? null} />;
}

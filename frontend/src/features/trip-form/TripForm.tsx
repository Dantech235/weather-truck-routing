import { zodResolver } from '@hookform/resolvers/zod';
import clsx from 'clsx';
import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import type { ApiError } from '../../api/client';
import type { Plan, PlanRequest } from '../../api/types';
import {
  formatThousands,
  nextQuarterHour,
  parseThousands,
  toDateTimeLocalValue,
} from '../../lib/format';
import { PlaceAutocomplete } from './PlaceAutocomplete';
import { formFieldFor, INTERVALS, tripFormSchema, type TripFormValues } from './schema';

interface Props {
  onSubmit: (body: PlanRequest) => void;
  submitting: boolean;
  error: ApiError | null;
  initial?: Plan['inputs'];
}

function defaults(initial?: Plan['inputs']): TripFormValues {
  if (!initial) {
    return {
      origin: null,
      destination: null,
      departureLocal: toDateTimeLocalValue(nextQuarterHour()),
      load: '45,000',
      interval: 25,
    };
  }
  const departure = new Date(initial.departure_utc);
  const future = departure.getTime() > Date.now() ? departure : nextQuarterHour();
  return {
    origin: initial.origin,
    destination: initial.destination,
    departureLocal: toDateTimeLocalValue(future),
    load: initial.load_lb.toLocaleString('en-US'),
    interval: (INTERVALS as readonly number[]).includes(initial.interval_mi)
      ? (initial.interval_mi as 10 | 25 | 50)
      : 25,
  };
}

export function TripForm({ onSubmit, submitting, error, initial }: Props) {
  const {
    control,
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<TripFormValues>({
    resolver: zodResolver(tripFormSchema),
    defaultValues: defaults(initial),
  });

  useEffect(() => {
    if (!error) return;
    const field = formFieldFor(error.field);
    if (field) setError(field, { type: 'server', message: error.message });
  }, [error, setError]);

  const submit = handleSubmit((v) => {
    if (!v.origin || !v.destination) return;
    onSubmit({
      origin: v.origin,
      destination: v.destination,
      departure: new Date(v.departureLocal).toISOString(),
      load_lb: parseThousands(v.load),
      interval_mi: v.interval,
    });
  });

  const loadField = register('load');
  const formError = error && !formFieldFor(error.field) ? error : null;

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="Trip details">
      <Controller
        control={control}
        name="origin"
        render={({ field }) => (
          <PlaceAutocomplete
            name="origin"
            label="Origin"
            placeholder="City or address"
            value={field.value}
            onChange={field.onChange}
            error={errors.origin?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="destination"
        render={({ field }) => (
          <PlaceAutocomplete
            name="destination"
            label="Destination"
            placeholder="City or address"
            value={field.value}
            onChange={field.onChange}
            error={errors.destination?.message}
          />
        )}
      />
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="departure" className="label">
            Departure (local)
          </label>
          <input
            id="departure"
            type="datetime-local"
            step={900}
            className={clsx('field', errors.departureLocal && 'field-error')}
            aria-invalid={Boolean(errors.departureLocal)}
            aria-describedby={errors.departureLocal ? 'departure-error' : undefined}
            {...register('departureLocal')}
          />
          {errors.departureLocal && (
            <p id="departure-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.departureLocal.message}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="load" className="label">
            Load (lb)
          </label>
          <input
            id="load"
            inputMode="numeric"
            autoComplete="off"
            className={clsx('field tabular-nums', errors.load && 'field-error')}
            aria-invalid={Boolean(errors.load)}
            aria-describedby={errors.load ? 'load-error' : undefined}
            {...loadField}
            onChange={(e) => {
              const formatted = formatThousands(e.target.value);
              setValue('load', formatted, { shouldValidate: Boolean(errors.load) });
            }}
          />
          {errors.load && (
            <p id="load-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.load.message}
            </p>
          )}
        </div>
      </div>
      <fieldset>
        <legend className="label">Checkpoint every</legend>
        <Controller
          control={control}
          name="interval"
          render={({ field }) => (
            <div
              role="radiogroup"
              aria-label="Checkpoint interval"
              className="grid grid-cols-3 rounded-xl border border-slate-200 bg-slate-100/80 p-1 dark:border-white/10 dark:bg-white/5"
            >
              {INTERVALS.map((mi) => (
                <label
                  key={mi}
                  className={clsx(
                    'cursor-pointer rounded-lg py-1.5 text-center text-sm font-medium transition-colors focus-within:ring-2 focus-within:ring-accent',
                    field.value === mi
                      ? 'bg-white text-accent shadow-sm dark:bg-white/15 dark:text-white'
                      : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
                  )}
                >
                  <input
                    type="radio"
                    className="sr-only"
                    name="interval"
                    value={mi}
                    checked={field.value === mi}
                    onChange={() => field.onChange(mi)}
                  />
                  {mi} mi
                </label>
              ))}
            </div>
          )}
        />
      </fieldset>
      {formError && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
        >
          {formError.message}
        </p>
      )}
      <button
        type="submit"
        className="btn-primary w-full"
        disabled={submitting}
        aria-busy={submitting}
      >
        {submitting ? (
          <span className="inline-flex items-center gap-2">
            <span
              className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
              aria-hidden
            />
            Planning routes…
          </span>
        ) : (
          'Plan routes'
        )}
      </button>
    </form>
  );
}

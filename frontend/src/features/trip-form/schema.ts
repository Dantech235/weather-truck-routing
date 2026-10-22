import { z } from 'zod';
import { parseThousands } from '../../lib/format';

export const INTERVALS = [10, 25, 50] as const;
export const MAX_LOAD_LB = 120_000;

export const placeSchema = z.object({
  label: z.string().min(1),
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
});

export const tripFormSchema = z.object({
  origin: placeSchema.nullable().refine((v) => v !== null, 'Choose an origin from the list.'),
  destination: placeSchema
    .nullable()
    .refine((v) => v !== null, 'Choose a destination from the list.'),
  departureLocal: z
    .string()
    .min(1, 'Choose a departure time.')
    .refine((v) => !Number.isNaN(new Date(v).getTime()), 'Enter a valid date and time.'),
  load: z
    .string()
    .refine((v) => !Number.isNaN(parseThousands(v)), 'Enter the load weight in pounds.')
    .refine((v) => parseThousands(v) >= 1, 'Load must be at least 1 lb.')
    .refine(
      (v) => parseThousands(v) <= MAX_LOAD_LB,
      `Load must be at most ${MAX_LOAD_LB.toLocaleString('en-US')} lb.`,
    ),
  interval: z.union([z.literal(10), z.literal(25), z.literal(50)]),
});

export type TripFormValues = z.input<typeof tripFormSchema>;

/** Map an API error field (e.g. "origin.lat") to a form field name. */
export function formFieldFor(apiField: string | null): keyof TripFormValues | null {
  if (!apiField) return null;
  const root = apiField.split('.')[0];
  switch (root) {
    case 'origin':
      return 'origin';
    case 'destination':
      return 'destination';
    case 'departure':
      return 'departureLocal';
    case 'load_lb':
      return 'load';
    case 'interval_mi':
      return 'interval';
    default:
      return null;
  }
}

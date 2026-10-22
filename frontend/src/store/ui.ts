import { create } from 'zustand';

export interface SelectedCheckpoint {
  route: string;
  index: number;
}

interface UIState {
  selectedRoute: string | null;
  hoveredRoute: string | null;
  selectedCheckpoint: SelectedCheckpoint | null;
  /** Forecast slider hour (0–48). Committed on pointer-up / throttled; never per input event. */
  sliderHour: number;
  playing: boolean;
  selectRoute: (label: string | null) => void;
  hoverRoute: (label: string | null) => void;
  selectCheckpoint: (cp: SelectedCheckpoint | null) => void;
  setSliderHour: (hour: number) => void;
  setPlaying: (playing: boolean) => void;
  reset: (selectedRoute: string | null) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  selectedRoute: null,
  hoveredRoute: null,
  selectedCheckpoint: null,
  sliderHour: 0,
  playing: false,
  selectRoute: (label) => set({ selectedRoute: label }),
  hoverRoute: (label) => set({ hoveredRoute: label }),
  selectCheckpoint: (cp) =>
    set((s) => ({ selectedCheckpoint: cp, selectedRoute: cp ? cp.route : s.selectedRoute })),
  setSliderHour: (hour) => set({ sliderHour: hour }),
  setPlaying: (playing) => set({ playing }),
  reset: (selectedRoute) =>
    set({
      selectedRoute,
      hoveredRoute: null,
      selectedCheckpoint: null,
      sliderHour: 0,
      playing: false,
    }),
}));

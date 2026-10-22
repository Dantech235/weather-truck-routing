export {};

declare global {
  interface Window {
    __reactCommits?: number;
    __truckMap?: {
      getLayer: (id: string) => unknown;
      project: (lngLat: [number, number]) => { x: number; y: number };
      getCanvas: () => HTMLCanvasElement;
    };
  }
}

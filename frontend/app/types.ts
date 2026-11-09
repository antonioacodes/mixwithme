export type Plugin = {
  name: string;
  kind:
    | "eq"
    | "compressor"
    | "limiter"
    | "reverb"
    | "delay"
    | "saturation"
    | "other";
  bypass: boolean;
};
export type Channel = {
  id: string;
  name: string;
  kind:
    | "vocal"
    | "backing"
    | "adlib"
    | "beat"
    | "bus"
    | "return"
    | "master"
    | "other";
  fader_db: number;
  pan: number;
  width: number;
  plugins: Plugin[];
};
export type Route = {
  source: string;
  target: string;
  kind: "output" | "send";
  gain_db: number;
};
export type Session = {
  daw: string;
  bpm: number;
  stage: "mix" | "master";
  beat_source: "stereo" | "multitrack";
  beat_already_limited: "yes" | "no" | "unknown";
  export_sample_rate: number;
  export_bit_depth: "16" | "24" | "32-float";
  listening_setup: string;
  intent: string;
  channels: Channel[];
  routes: Route[];
};
export type Track = { id: string; title: string; session: Session };
export type Hypothesis = {
  id: string;
  hypothesis: string;
  evidence: string;
  confidence: string;
  question: string;
};
export type Result = {
  engine: string;
  sha256: string;
  metrics: {
    duration_s: number;
    sample_rate_hz: number;
    channels: number;
    subtype: string;
    silent: boolean;
    sample_peak_dbfs: number | null;
    rms_dbfs: number | null;
    crest_db: number | null;
    lr_correlation: number | null;
    mono_downmix_change_db: number | null;
    band_energy_pct: Record<string, number | null>;
    window_rms_dbfs: (number | null)[];
    [key: string]: unknown;
  };
  scores: {
    category: string;
    score: number | null;
    reason: string;
    provisional: boolean;
  }[];
  hypotheses: Hypothesis[];
  warnings: string[];
  methods: Record<string, string>;
};
export type Version = {
  id: string;
  track_id: string;
  label: string;
  status: string;
  session: Session;
  created_at: string;
  error: string | null;
  result: Result | null;
  answers?: { question_id: string; answer: string }[];
};
export const initialSession: Session = {
  daw: "FL Studio",
  bpm: 140,
  stage: "mix",
  beat_source: "stereo",
  beat_already_limited: "unknown",
  export_sample_rate: 48000,
  export_bit_depth: "24",
  listening_setup: "",
  intent: "",
  channels: [
    {
      id: "vocal",
      name: "Vocal principal",
      kind: "vocal",
      fader_db: 0,
      pan: 0,
      width: 1,
      plugins: [],
    },
    {
      id: "beat",
      name: "Beat",
      kind: "beat",
      fader_db: 0,
      pan: 0,
      width: 1,
      plugins: [],
    },
    {
      id: "bus",
      name: "Vocal bus",
      kind: "bus",
      fader_db: 0,
      pan: 0,
      width: 1,
      plugins: [],
    },
    {
      id: "master",
      name: "Master",
      kind: "master",
      fader_db: 0,
      pan: 0,
      width: 1,
      plugins: [],
    },
  ],
  routes: [
    { source: "vocal", target: "bus", kind: "output", gain_db: 0 },
    { source: "bus", target: "master", kind: "output", gain_db: 0 },
    { source: "beat", target: "master", kind: "output", gain_db: 0 },
  ],
};

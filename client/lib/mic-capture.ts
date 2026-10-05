import {
  CAPTURE_SAMPLE_RATE,
  Downsampler,
  FRAME_SAMPLES,
  FrameChunker,
  type Samples,
} from "@/lib/pcm";

export interface MicCapture {
  close(): void;
}

export type OpenMic = (
  onFrame: (frame: Samples) => void,
) => Promise<MicCapture>;

export class MicUnsupportedError extends Error {
  constructor() {
    super("Microphone capture is not supported");
    this.name = "MicUnsupportedError";
  }
}

const WORKLET_URL = "/worklets/pcm-capture.js";
const RESUME_TIMEOUT_MS = 1000;

export const openMicCapture: OpenMic = async (onFrame) => {
  if (
    !navigator.mediaDevices?.getUserMedia ||
    typeof AudioWorkletNode === "undefined"
  ) {
    throw new MicUnsupportedError();
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  });
  let context: AudioContext | undefined;
  try {
    context = new AudioContext();
    await context.audioWorklet.addModule(WORKLET_URL);
    if (context.state === "suspended") {
      await Promise.race([
        context.resume(),
        new Promise<void>((resolve) => setTimeout(resolve, RESUME_TIMEOUT_MS)),
      ]);
    }
    const source = context.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(context, "pcm-capture");
    const downsampler = new Downsampler(
      context.sampleRate,
      CAPTURE_SAMPLE_RATE,
    );
    const chunker = new FrameChunker(FRAME_SAMPLES);
    node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      for (const frame of chunker.push(downsampler.push(event.data)))
        onFrame(frame);
    };
    source.connect(node);
    // 出力先につながっていないノードはブラウザが処理しないので、無音で destination へつなぐ
    const mute = context.createGain();
    mute.gain.value = 0;
    node.connect(mute).connect(context.destination);

    const opened = context;
    return {
      close() {
        node.port.onmessage = null;
        source.disconnect();
        node.disconnect();
        stream.getTracks().forEach((track) => track.stop());
        void opened.close();
      },
    };
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    void context?.close();
    throw error;
  }
};

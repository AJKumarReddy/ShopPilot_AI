export type VoiceState = "idle" | "listening" | "speaking";
interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}
interface BrowserRecognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type VoiceWindow = Window & {
  SpeechRecognition?: new () => BrowserRecognition;
  webkitSpeechRecognition?: new () => BrowserRecognition;
};
export interface VoiceProvider {
  readonly supported: boolean;
  listen(
    onTranscript: (text: string, final: boolean) => void,
    onError: (message: string) => void,
  ): void;
  stopListening(): void;
  speak(text: string): void;
  cancelSpeech(): void;
  dispose(): void;
}
export class BrowserVoiceProvider implements VoiceProvider {
  private recognition: BrowserRecognition | null = null;
  readonly supported: boolean;
  constructor(private onState: (state: VoiceState) => void) {
    const browser = window as VoiceWindow;
    const Recognition =
      browser.SpeechRecognition || browser.webkitSpeechRecognition;
    this.supported = !!Recognition;
    if (Recognition) this.recognition = new Recognition();
  }
  listen(
    onTranscript: (text: string, final: boolean) => void,
    onError: (message: string) => void,
  ) {
    this.cancelSpeech();
    if (!this.recognition) {
      onError(
        "Voice input isn't supported in this browser. You can still type your request.",
      );
      return;
    }
    const recognition = this.recognition;
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const result = event.results[event.resultIndex];
      onTranscript(result[0].transcript, result.isFinal);
    };
    recognition.onerror = (event) => {
      this.onState("idle");
      onError(
        event.error === "not-allowed"
          ? "Microphone permission was denied. You can use text instead."
          : "I couldn't hear that. Please try again or type your message.",
      );
    };
    recognition.onend = () => this.onState("idle");
    try {
      recognition.start();
      this.onState("listening");
    } catch {
      onError("The microphone is already active.");
    }
  }
  stopListening() {
    this.recognition?.stop();
    this.onState("idle");
  }
  speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    this.cancelSpeech();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.onend = () => this.onState("idle");
    utterance.onerror = () => this.onState("idle");
    this.onState("speaking");
    window.speechSynthesis.speak(utterance);
  }
  cancelSpeech() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    this.onState("idle");
  }
  dispose() {
    this.recognition?.abort();
    this.cancelSpeech();
  }
}

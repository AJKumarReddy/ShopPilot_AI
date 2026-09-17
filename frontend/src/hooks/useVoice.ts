"use client";
import { useEffect, useRef, useState } from "react";
import { BrowserVoiceProvider, type VoiceState } from "@/lib/voice";
export function useVoice(
  onFinal: (text: string) => void,
  onError: (message: string) => void,
) {
  const provider = useRef<BrowserVoiceProvider | null>(null);
  const finalRef = useRef(onFinal);
  finalRef.current = onFinal;
  const errorRef = useRef(onError);
  errorRef.current = onError;
  const [state, setState] = useState<VoiceState>("idle");
  const [supported, setSupported] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [readAloud, setReadAloud] = useState(false);
  useEffect(() => {
    provider.current = new BrowserVoiceProvider(setState);
    setSupported(provider.current.supported);
    return () => {
      provider.current?.dispose();
    };
  }, []);
  return {
    state,
    supported,
    transcript,
    enabled,
    readAloud,
    setEnabled(value: boolean) {
      setEnabled(value);
      if (!value) {
        provider.current?.stopListening();
        provider.current?.cancelSpeech();
      }
    },
    setReadAloud(value: boolean) {
      setReadAloud(value);
      if (!value) provider.current?.cancelSpeech();
    },
    start() {
      if (!enabled) return;
      setTranscript("");
      provider.current?.listen(
        (text, final) => {
          setTranscript(text);
          if (final) finalRef.current(text);
        },
        (error) => errorRef.current(error),
      );
    },
    stop() {
      provider.current?.stopListening();
    },
    speak(text: string) {
      if (readAloud && enabled) provider.current?.speak(text);
    },
    cancel() {
      provider.current?.cancelSpeech();
    },
  };
}

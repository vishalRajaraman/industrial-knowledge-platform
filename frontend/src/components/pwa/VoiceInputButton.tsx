"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Mic } from 'lucide-react';

interface VoiceInputButtonProps {
  onTranscriptionComplete: (text: string) => void;
  onInterimTranscription?: (text: string) => void;
}

export function VoiceInputButton({ onTranscriptionComplete, onInterimTranscription }: VoiceInputButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    // Initialize SpeechRecognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsRecording(true);
        setErrorMsg(null);
        // Haptic feedback for Android
        if (navigator.vibrate) {
          navigator.vibrate([200, 100, 200]);
        }
      };

      recognition.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        if (interimTranscript && onInterimTranscription) {
          onInterimTranscription(interimTranscript);
        }
        
        if (finalTranscript) {
          onTranscriptionComplete(finalTranscript);
        }
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsRecording(false);
        setErrorMsg(`Microphone error: ${event.error}`);
        if (navigator.vibrate) navigator.vibrate(500); // long error vibration
      };

      recognition.onend = () => {
        setIsRecording(false);
        if (navigator.vibrate) navigator.vibrate(100);
      };

      recognitionRef.current = recognition;
    } else {
      setErrorMsg("Speech Recognition API not supported in this browser.");
    }
  }, [onInterimTranscription, onTranscriptionComplete]);

  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    if (recognitionRef.current && !isRecording) {
      try {
        recognitionRef.current.start();
      } catch (e) {
        // Already started
      }
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    e.preventDefault();
    if (recognitionRef.current && isRecording) {
      recognitionRef.current.stop();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div className="relative flex items-center justify-center">
        {/* Pulsing ring when recording */}
        <div 
          className={`absolute rounded-full bg-red-400 transition-all duration-300 ease-in-out ${
            isRecording ? 'w-32 h-32 opacity-40 animate-ping' : 'w-24 h-24 opacity-0'
          }`}
        />
        
        {/* Main PTT Button */}
        <button
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp} // Stop if finger drags off
          className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center text-white shadow-lg transition-transform duration-150 active:scale-95 touch-none select-none ${
            isRecording ? 'bg-red-600' : 'bg-orange-500 hover:bg-orange-600'
          }`}
          disabled={!recognitionRef.current}
          aria-label="Push to Talk"
        >
          <Mic size={40} strokeWidth={2} />
        </button>
      </div>
      
      <p className="mt-6 text-lg font-semibold text-gray-700">
        {isRecording ? "Release to Send" : "Hold to Speak"}
      </p>
      
      {errorMsg && (
        <p className="mt-2 text-sm text-red-500 font-medium max-w-xs text-center">
          {errorMsg}
        </p>
      )}
    </div>
  );
}

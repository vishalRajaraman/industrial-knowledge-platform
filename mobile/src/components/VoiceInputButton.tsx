import React, { useState, useEffect } from 'react';
import { Pressable, StyleSheet, Text, View, Animated, Platform, Alert } from 'react-native';
import { useSpeechRecognitionEvent, ExpoSpeechRecognitionModule } from 'expo-speech-recognition';
import * as Haptics from 'expo-haptics';
import { Mic } from 'lucide-react-native';

interface VoiceInputButtonProps {
  onTranscriptionComplete: (text: string) => void;
  onInterimTranscription?: (text: string) => void;
}

export function VoiceInputButton({ onTranscriptionComplete, onInterimTranscription }: VoiceInputButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [pulseAnim] = useState(new Animated.Value(1));

  // Listeners for expo-speech-recognition
  useSpeechRecognitionEvent("start", () => {
    setIsRecording(true);
    startPulse();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
  });

  useSpeechRecognitionEvent("end", () => {
    stopRecordingUI();
  });

  useSpeechRecognitionEvent("error", (event) => {
    console.error('Speech error:', event.error);
    stopRecordingUI();
  });

  useSpeechRecognitionEvent("result", (event) => {
    const text = event.results[0]?.transcript;
    if (text) {
      if (event.isFinal) {
        onTranscriptionComplete(text);
      } else if (onInterimTranscription) {
        onInterimTranscription(text);
      }
    }
  });

  const startPulse = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.2,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
      ])
    ).start();
  };

  const stopRecordingUI = () => {
    setIsRecording(false);
    pulseAnim.setValue(1);
    pulseAnim.stopAnimation();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  };

  const handlePressIn = async () => {
    try {
      const { status } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Microphone and speech recognition permissions are required.');
        return;
      }
      
      ExpoSpeechRecognitionModule.start({
        lang: "en-US",
        interimResults: true,
        requiresOnDeviceRecognition: true, // prefer offline if available
      });
    } catch (e) {
      console.error('Failed to start voice recognition:', e);
    }
  };

  const handlePressOut = async () => {
    try {
      ExpoSpeechRecognitionModule.stop();
    } catch (e) {
      console.error('Failed to stop voice recognition:', e);
    }
  };

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.pulseRing, { transform: [{ scale: pulseAnim }], opacity: isRecording ? 0.4 : 0 }]} />
      <Pressable
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          isRecording && styles.buttonRecording,
        ]}
      >
        <Mic size={40} color="white" />
      </Pressable>
      <Text style={styles.helpText}>
        {isRecording ? "Release to Send" : "Hold to Speak"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  pulseRing: {
    position: 'absolute',
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#FF6B6B',
    zIndex: 0,
  },
  button: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#FF8C00', // Hazard Orange for high visibility
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 4.65,
  },
  buttonPressed: {
    transform: [{ scale: 0.95 }],
    backgroundColor: '#E67300',
  },
  buttonRecording: {
    backgroundColor: '#FF3B30',
  },
  helpText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '600',
    color: '#4A5568',
  },
});

import React, { useState } from 'react';
import { StyleSheet, Text, View, SafeAreaView, TextInput, ActivityIndicator } from 'react-native';
import { VoiceInputButton } from '../components/VoiceInputButton';

export function SearchScreen() {
  const [query, setQuery] = useState('');
  const [interimText, setInterimText] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<string | null>(null);

  const handleSearch = async (text: string) => {
    if (!text.trim()) return;
    
    setQuery(text);
    setInterimText('');
    setIsSearching(true);
    setSearchResult(null);

    // Mock sending the query to the backend search API
    // In production, this would hit the API Gateway search endpoints
    try {
      // Simulate network latency
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      setSearchResult(`Found 3 documents and 1 equipment tag matching "${text}".`);
    } catch (e) {
      setSearchResult("Search failed. Are you offline?");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Field Tech Query</Text>
        <Text style={styles.subtitle}>Hold the mic button and speak your query</Text>
      </View>

      <View style={styles.content}>
        {/* Search Bar / Input Display */}
        <View style={styles.searchBox}>
          <TextInput
            style={styles.input}
            value={query}
            onChangeText={setQuery}
            placeholder="Type or speak a query..."
            placeholderTextColor="#A0AEC0"
            multiline
            editable={!isSearching}
          />
        </View>

        {/* Interim Speech Display */}
        {interimText ? (
          <View style={styles.interimContainer}>
            <Text style={styles.interimLabel}>Hearing:</Text>
            <Text style={styles.interimText}>{interimText}</Text>
          </View>
        ) : null}

        {/* Results Area */}
        <View style={styles.resultsArea}>
          {isSearching ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#007AFF" />
              <Text style={styles.loadingText}>Searching Knowledge Graph...</Text>
            </View>
          ) : searchResult ? (
            <View style={styles.resultCard}>
              <Text style={styles.resultText}>{searchResult}</Text>
            </View>
          ) : null}
        </View>
      </View>

      <View style={styles.footer}>
        <VoiceInputButton 
          onInterimTranscription={(text) => setInterimText(text)}
          onTranscriptionComplete={(text) => {
            setInterimText('');
            setQuery(text);
            handleSearch(text);
          }}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F7FAFC',
  },
  header: {
    padding: 24,
    paddingTop: 40,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1A202C',
  },
  subtitle: {
    fontSize: 16,
    color: '#718096',
    marginTop: 8,
  },
  content: {
    flex: 1,
    padding: 20,
  },
  searchBox: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  input: {
    fontSize: 18,
    color: '#2D3748',
    minHeight: 40,
  },
  interimContainer: {
    marginTop: 16,
    padding: 16,
    backgroundColor: '#EBF8FF',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#3182CE',
  },
  interimLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#3182CE',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  interimText: {
    fontSize: 16,
    color: '#2B6CB0',
    fontStyle: 'italic',
  },
  resultsArea: {
    flex: 1,
    marginTop: 24,
    justifyContent: 'center',
  },
  loadingContainer: {
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#4A5568',
  },
  resultCard: {
    backgroundColor: '#FFFFFF',
    padding: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#CBD5E0',
  },
  resultText: {
    fontSize: 18,
    color: '#2D3748',
    textAlign: 'center',
  },
  footer: {
    paddingBottom: 30,
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
});

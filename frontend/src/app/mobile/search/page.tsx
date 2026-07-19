"use client";

import React, { useState } from 'react';
import { VoiceInputButton } from '@/components/pwa/VoiceInputButton';
import { Loader2 } from 'lucide-react';

export default function MobileSearchPage() {
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

    try {
      // Call the Orchestrator API directly (served on the same origin via API Gateway)
      const response = await fetch('/api/v1/search/vector', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          query: text,
          top_k: 5
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      
      // Parse the results from the stub response
      if (data.results && data.results.length > 0) {
        setSearchResult(`Found ${data.results.length} relevant items in the Knowledge Graph for "${text}".`);
      } else {
        setSearchResult(`No specific results found for "${text}".`);
      }
    } catch (e) {
      console.error(e);
      setSearchResult("Search failed. Ensure you have network connectivity to the API.");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="flex flex-col h-screen max-h-screen bg-slate-50 font-sans overflow-hidden">
      <header className="p-6 pt-10 bg-white border-b border-slate-200 shrink-0 shadow-sm z-10">
        <h1 className="text-2xl font-bold text-slate-900">Field Tech Query</h1>
        <p className="text-sm text-slate-500 mt-1">Hold the mic button and speak your query</p>
      </header>

      <main className="flex-1 flex flex-col p-6 overflow-y-auto">
        {/* Search Bar / Input Display */}
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm min-h-[80px]">
          <textarea
            className="w-full h-full text-lg text-slate-800 bg-transparent resize-none focus:outline-none"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type or speak a query..."
            disabled={isSearching}
            rows={2}
          />
        </div>

        {/* Interim Speech Display */}
        {interimText && (
          <div className="mt-4 p-4 bg-sky-50 rounded-lg border-l-4 border-sky-500">
            <p className="text-xs font-bold text-sky-600 uppercase mb-1">Hearing:</p>
            <p className="text-base text-sky-700 italic">{interimText}</p>
          </div>
        )}

        {/* Results Area */}
        <div className="flex-1 mt-6 flex flex-col justify-center">
          {isSearching ? (
            <div className="flex flex-col items-center text-slate-500">
              <Loader2 className="w-10 h-10 animate-spin text-sky-500 mb-4" />
              <p className="text-base font-medium">Searching Knowledge Graph...</p>
            </div>
          ) : searchResult ? (
            <div className="bg-white p-6 rounded-xl border border-slate-300 shadow-sm">
              <p className="text-lg text-slate-800 text-center">{searchResult}</p>
            </div>
          ) : null}
        </div>
      </main>

      <footer className="shrink-0 pb-10 bg-white border-t border-slate-200 z-10">
        <VoiceInputButton 
          onInterimTranscription={(text) => setInterimText(text)}
          onTranscriptionComplete={(text) => {
            setInterimText('');
            setQuery(text);
            handleSearch(text);
          }}
        />
      </footer>
    </div>
  );
}

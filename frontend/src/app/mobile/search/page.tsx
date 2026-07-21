"use client";

import React, { useState, useEffect } from 'react';
import { VoiceInputButton } from '@/components/pwa/VoiceInputButton';
import { Loader2, WifiOff } from 'lucide-react';
import { useNetwork } from '@/hooks/useNetwork';
import { db } from '@/lib/db';
import { syncProceduresToLocal } from '@/services/syncService';

export default function MobileSearchPage() {
  const [query, setQuery] = useState('');
  const [interimText, setInterimText] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<string | null>(null);
  
  const { isOnline } = useNetwork();

  // Initial Sync
  useEffect(() => {
    // We safely call this here because it runs entirely on the client
    syncProceduresToLocal();
  }, []);

  const handleSearch = async (text: string) => {
    if (!text.trim()) return;
    
    setQuery(text);
    setInterimText('');
    setIsSearching(true);
    setSearchResult(null);

    try {
      if (isOnline) {
        // ONLINE MODE: Call the Orchestrator API directly
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
        
        if (data.results && data.results.length > 0) {
          setSearchResult(`Found ${data.results.length} relevant items in the Knowledge Graph for "${text}".`);
        } else {
          setSearchResult(`No specific results found for "${text}".`);
        }
      } else {
        // OFFLINE MODE: Fallback to local Dexie IndexedDB
        if (typeof window !== 'undefined' && db) {
          const lowerText = text.toLowerCase();
          
          // Simple local text search across title and content
          const offlineResults = await db.safetyProcedures
            .filter(proc => proc.title.toLowerCase().includes(lowerText) || proc.content.toLowerCase().includes(lowerText))
            .toArray();

          if (offlineResults.length > 0) {
            const firstProc = offlineResults[0];
            setSearchResult(`[OFFLINE LOCAL MATCH] ${firstProc.title}: ${firstProc.content}`);
          } else {
            setSearchResult(`No local procedures found offline for "${text}".`);
          }
        } else {
           setSearchResult("Offline search is not supported in this environment.");
        }
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

      {!isOnline && (
        <div className="bg-amber-100 border-l-4 border-amber-500 p-3 mx-4 mt-4 rounded-r flex items-center gap-3">
          <WifiOff className="text-amber-600 w-5 h-5 shrink-0" />
          <p className="text-amber-800 text-sm font-semibold">
            OFFLINE: Displaying locally cached safety procedures.
          </p>
        </div>
      )}

      <main className="flex-1 flex flex-col p-6 overflow-y-auto">
        {/* Search Bar / Input Display */}
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm min-h-[80px] flex gap-3">
          <textarea
            className="w-full h-full text-lg text-slate-800 bg-transparent resize-none focus:outline-none"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch(query);
              }
            }}
            placeholder="Type or speak a query..."
            disabled={isSearching}
            rows={2}
          />
          <button 
            onClick={() => handleSearch(query)}
            disabled={!query.trim() || isSearching}
            className="self-end bg-sky-500 hover:bg-sky-600 disabled:bg-slate-300 text-white rounded-lg px-4 py-2 font-medium transition-colors"
          >
            Search
          </button>
        </div>

        {/* Interim Speech Display */}
        {interimText && (
          <div className="mt-4 p-4 bg-sky-50 rounded-lg border-l-4 border-sky-500">
            <p className="text-xs font-bold text-sky-600 uppercase mb-1">Hearing:</p>
            <p className="text-base text-sky-700 italic">{interimText}</p>
          </div>
        )}

        {/* Results Area */}
        <div className="flex-1 mt-6 flex flex-col justify-start">
          {isSearching ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <Loader2 className="w-10 h-10 animate-spin text-sky-500 mb-4" />
              <p className="text-base font-medium">
                {isOnline ? "Searching Knowledge Graph..." : "Searching Local Cache..."}
              </p>
            </div>
          ) : searchResult ? (
            <div className={`p-6 rounded-xl border shadow-sm ${!isOnline ? 'bg-amber-50 border-amber-200' : 'bg-white border-slate-300'}`}>
              <p className="text-lg text-slate-800 text-left whitespace-pre-line leading-relaxed">{searchResult}</p>
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

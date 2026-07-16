'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Database, Clock, FileText, ChevronRight, Search } from 'lucide-react';
import { api } from '@/services/api';
import { VersionRecord, Epic, Feature, Story } from '@/services/mockData';
import { Button } from '@/components/common/Button';
import { cn, formatDate } from '@/lib/utils';

export default function VersioningPage() {
  const params = useParams();
  const projectId = params?.projectId as string;

  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState<VersionRecord[]>([]);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  
  const [activeTab, setActiveTab] = useState<'epic' | 'feature' | 'story'>('epic');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    Promise.all([
      api.getVersions(projectId),
      api.getEpics(projectId),
      api.getFeatures(projectId),
      api.getStories(projectId)
    ]).then(([versionsData, epicsData, featuresData, storiesData]) => {
      setVersions(versionsData);
      setEpics(epicsData);
      setFeatures(featuresData);
      setStories(storiesData);
      setLoading(false);
    });
  }, [projectId]);

  const filteredVersions = versions
    .filter(v => v.entityType === activeTab)
    .filter(v => 
      v.author.toLowerCase().includes(searchQuery.toLowerCase()) || 
      v.changes.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.entityId.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  const getEntityTitle = (entityId: string, type: 'epic' | 'feature' | 'story') => {
    if (type === 'epic') return epics.find(e => e.id === entityId)?.title || entityId;
    if (type === 'feature') return features.find(f => f.id === entityId)?.title || entityId;
    if (type === 'story') {
      const s = stories.find(s => s.id === entityId);
      return s ? `${s.usId} - ${s.summary.substring(0, 40)}...` : entityId;
    }
    return entityId;
  };

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading version history...</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background text-foreground relative">
      <div className="p-6 pb-4 shrink-0 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Version Control</h1>
            <p className="text-[13px] text-muted-foreground mt-1">Track changes and manage version history for all PRD assets.</p>
          </div>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-muted-foreground" />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 mb-2 justify-between items-center">
          {/* Tabs */}
          <div className="flex bg-muted/50 rounded-lg p-1 border border-border">
            <button 
              onClick={() => setActiveTab('epic')}
              className={cn("px-4 py-2 rounded text-sm font-medium transition-colors", activeTab === 'epic' ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}
            >
              Epics
            </button>
            <button 
              onClick={() => setActiveTab('feature')}
              className={cn("px-4 py-2 rounded text-sm font-medium transition-colors", activeTab === 'feature' ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}
            >
              Features
            </button>
            <button 
              onClick={() => setActiveTab('story')}
              className={cn("px-4 py-2 rounded text-sm font-medium transition-colors", activeTab === 'story' ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}
            >
              User Stories
            </button>
          </div>

          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input 
              type="text" 
              placeholder={`Search ${activeTab} versions...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 h-[32px] bg-background border border-input rounded-lg text-[13px] focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-muted/10">
        <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-[13px] text-left">
            <thead className="bg-muted/50 text-muted-foreground text-[11px] uppercase font-bold border-b border-border tracking-wider">
              <tr>
                <th className="px-5 py-3">Entity</th>
                <th className="px-5 py-3">Version</th>
                <th className="px-5 py-3">Date & Time</th>
                <th className="px-5 py-3">Author</th>
                <th className="px-5 py-3">Change Description</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredVersions.length > 0 ? (
                filteredVersions.map((v) => (
                  <tr key={v.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-5 py-3 font-medium text-foreground">
                      <div className="flex flex-col">
                        <span className="text-[13px] leading-tight">{getEntityTitle(v.entityId, v.entityType)}</span>
                        <span className="text-[11px] text-muted-foreground uppercase mt-0.5">{v.entityId}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className="bg-primary/10 text-primary font-bold px-2 py-0.5 rounded text-[11px]">
                        {v.version}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      <div className="flex items-center gap-1.5 text-[12px]">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(v.timestamp).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      {v.author}
                    </td>
                    <td className="px-5 py-3 max-w-xs truncate" title={v.changes}>
                      {v.changes}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] font-bold text-primary">
                        View Diff <ChevronRight className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    <FileText className="w-8 h-8 mx-auto mb-3 opacity-20" />
                    No version history found for {activeTab}s.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

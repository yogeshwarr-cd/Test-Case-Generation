'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const ConnectionToast: React.FC = () => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let triggered = false;
    const handleFailure = () => {
      // Show only once briefly to avoid user fatigue
      if (!triggered) {
        triggered = true;
        setShow(true);
        setTimeout(() => {
          setShow(false);
        }, 5000); // hide after 5 seconds
      }
    };

    window.addEventListener('api-connection-failure', handleFailure);
    return () => {
      window.removeEventListener('api-connection-failure', handleFailure);
    };
  }, []);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 50, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3 }}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 bg-zinc-950/90 text-amber-500 border border-amber-500/20 backdrop-blur-md rounded-xl shadow-2xl"
        >
          <AlertTriangle className="w-5 h-5 flex-shrink-0 animate-pulse" />
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-zinc-100">Using demo data</span>
            <span className="text-[10px] text-zinc-400">Backend not reachable.</span>
          </div>
          <button
            onClick={() => setShow(false)}
            className="p-1 hover:bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

import { create } from 'zustand';
import { UploadedDocument, ProcessingStep, RequirementCategory } from '@/lib/types/document';

interface IntakeState {
  uploadedDoc: UploadedDocument | null;
  processingSteps: ProcessingStep[];
  processingPercent: number;
  extractedRequirements: RequirementCategory[];
  isProcessing: boolean;
  startProcessing: (docName: string, fileSize: string) => void;
  setExtractedRequirements: (reqs: RequirementCategory[]) => void;
  resetIntake: () => void;
}

const initialSteps: ProcessingStep[] = [
  { time: 'In Progress', label: 'Document Upload', status: 'pending' },
  { time: 'Pending', label: 'Text Extraction', status: 'pending' },
  { time: 'Pending', label: 'Requirement Analysis', status: 'pending' },
  { time: 'Pending', label: 'Section Categorization', status: 'pending' },
  { time: 'Pending', label: 'Validation', status: 'pending' }
];

export const useIntakeStore = create<IntakeState>((set, get) => ({
  uploadedDoc: null,
  processingSteps: initialSteps,
  processingPercent: 0,
  extractedRequirements: [],
  isProcessing: false,

  startProcessing: (docName, fileSize) => {
    set({
      uploadedDoc: {
        name: docName,
        uploaded_at: new Date().toLocaleString(),
        file_size: fileSize,
        total_pages: Math.floor(Math.random() * 50) + 10
      },
      isProcessing: true,
      processingPercent: 0,
      processingSteps: initialSteps.map((s, idx) => idx === 0 ? { ...s, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), status: 'processing' } : s)
    });

    const interval = setInterval(() => {
      const { processingPercent, processingSteps } = get();
      if (processingPercent >= 100) {
        clearInterval(interval);
        set({ isProcessing: false });
        return;
      }

      const nextPercent = Math.min(processingPercent + 25, 100);
      const stepIdx = Math.floor(nextPercent / 25) - 1;

      const updatedSteps = processingSteps.map((step, idx) => {
        if (idx === stepIdx) {
          return {
            ...step,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            status: 'completed' as const
          };
        }
        if (idx === stepIdx + 1 && idx < processingSteps.length) {
          return {
            ...step,
            time: 'In Progress',
            status: 'processing' as const
          };
        }
        return step;
      });

      set({
        processingPercent: nextPercent,
        processingSteps: updatedSteps
      });
      
      if (nextPercent === 100) {
        set({
          extractedRequirements: [
            {
              id: 'functional',
              label: 'Functional Requirements',
              items: [
                { id: 'f1', text: 'User authentication and authorization with OAuth 2.0 support' },
                { id: 'f2', text: 'Product catalog management with hierarchical categories' },
                { id: 'f3', text: 'Shopping cart with save for later functionality' },
                { id: 'f4', text: 'Multi-step checkout process with guest checkout option' },
                { id: 'f5', text: 'Payment processing integration (Stripe, PayPal, Apple Pay)' }
              ]
            },
            {
              id: 'business',
              label: 'Business Rules',
              items: [
                { id: 'b1', text: 'Orders exceeding $100 trigger free standard shipping eligibility' },
                { id: 'b2', text: 'Failed payment transactions must retry up to 3 times before cancellation' }
              ]
            },
            {
              id: 'nfr',
              label: 'Non-Functional Requirements',
              items: [
                { id: 'n1', text: 'Page load times must remain below 1.5 seconds for core pages' },
                { id: 'n2', text: 'All data transmissions must be encrypted using TLS 1.3' }
              ]
            }
          ]
        });
      }
    }, 1500);
  },

  setExtractedRequirements: (reqs) => set({ extractedRequirements: reqs }),
  resetIntake: () => set({ uploadedDoc: null, processingSteps: initialSteps, processingPercent: 0, extractedRequirements: [], isProcessing: false })
}));

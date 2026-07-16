'use client';

import React from 'react';
import { Badge } from '../common/Badge';

export const ValidationBadge = ({ passed }: { passed: boolean }) => {
  return (
    <Badge variant={passed ? 'active' : 'danger'}>
      {passed ? 'Passed' : 'Failed'}
    </Badge>
  );
};

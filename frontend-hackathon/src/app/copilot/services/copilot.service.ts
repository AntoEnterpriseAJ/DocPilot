import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { RewriteSectionRequest, RewriteSectionResponse } from '../models/copilot.models';

@Injectable({ providedIn: 'root' })
export class CopilotService {
  private readonly http = inject(HttpClient);

  rewriteSection(req: RewriteSectionRequest): Observable<RewriteSectionResponse> {
    return this.http.post<RewriteSectionResponse>(
      '/api/documents/rewrite-section',
      req,
    );
  }
}

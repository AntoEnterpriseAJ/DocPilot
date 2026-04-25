import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CaseStore, CaseDocument } from '../case.store';
import { SyncCheckService } from '../../sync-check/services/sync-check.service';
import {
  CompetencyMapping,
  CrossValidationResult,
  ExtractedDocument,
  GuardViolation,
} from '../../sync-check/models/sync.models';
import { forkJoin, of, switchMap } from 'rxjs';

@Component({
  selector: 'app-sync-tool',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sync-tool.component.html',
  styleUrl: './sync-tool.component.scss',
})
export class SyncToolComponent {
  private readonly store = inject(CaseStore);
  private readonly service = inject(SyncCheckService);

  protected readonly fdId = signal<string | null>(null);
  protected readonly planId = signal<string | null>(null);
  protected readonly running = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<CrossValidationResult | null>(null);
  protected readonly mapping = signal<CompetencyMapping | null>(null);
  protected readonly mappingError = signal<string | null>(null);
  protected readonly mappingRunning = signal(false);

  protected readonly fdOptions = computed(() => this.store.documentsByKind().fd);
  protected readonly planOptions = computed(() => this.store.documentsByKind().plan);

  constructor() {
    queueMicrotask(() => {
      if (!this.fdId() && this.fdOptions()[0]) this.fdId.set(this.fdOptions()[0].id);
      if (!this.planId() && this.planOptions()[0]) this.planId.set(this.planOptions()[0].id);
    });
  }

  protected canRun(): boolean {
    return !!this.fdId() && !!this.planId() && !this.running();
  }

  protected onPickFd(e: Event): void {
    this.fdId.set((e.target as HTMLSelectElement).value || null);
  }
  protected onPickPlan(e: Event): void {
    this.planId.set((e.target as HTMLSelectElement).value || null);
  }

  /** Parse a doc if not already parsed; otherwise return cached. */
  private getParsed(doc: CaseDocument) {
    if (doc.parsed) return of(doc.parsed as ExtractedDocument);
    return this.service.parse(doc.file).pipe(
      switchMap((parsed) => {
        this.store.updateDocument(doc.id, { parsed });
        this.store.setDocumentStatus(doc.id, { parsed: true });
        return of(parsed);
      }),
    );
  }

  protected run(): void {
    const fd = this.store.documents().find((d) => d.id === this.fdId());
    const plan = this.store.documents().find((d) => d.id === this.planId());
    if (!fd || !plan) return;

    this.error.set(null);
    this.result.set(null);
    this.mapping.set(null);
    this.mappingError.set(null);
    this.mappingRunning.set(false);
    this.running.set(true);

    forkJoin({ fd: this.getParsed(fd), plan: this.getParsed(plan) })
      .pipe(switchMap(({ fd, plan }) =>
        this.service.crossValidate(fd, plan).pipe(
          switchMap((res) => {
            // Kick off competency mapping in the background — non-blocking.
            this.runMapping(fd, plan);
            return of(res);
          }),
        ),
      ))
      .subscribe({
        next: (res) => {
          this.running.set(false);
          this.result.set(res);
          this.store.setToolResult('sync', res);
        },
        error: (err) => {
          this.running.set(false);
          this.error.set(err?.error?.detail || err?.message || 'Sync check failed');
        },
      });
  }

  private runMapping(fd: ExtractedDocument, plan: ExtractedDocument): void {
    this.mappingRunning.set(true);
    // Explicitly opt into Claude suggestions so the AI-recommended block
    // is populated whenever there are plan-only competencies the FD hasn't declared.
    this.service.mapCompetencies(fd, plan, true).subscribe({
      next: (cm) => {
        this.mappingRunning.set(false);
        this.mapping.set(cm);
      },
      error: (err) => {
        this.mappingRunning.set(false);
        this.mappingError.set(err?.error?.detail || err?.message || 'Competency mapping failed');
      },
    });
  }

  protected violationStatus(v: GuardViolation): string {
    return v.code.includes('mismatch') ? '⚠' : '✗';
  }

  protected counts() {
    const r = this.result();
    if (!r) return { ok: 0, warn: 0, miss: 0 };
    const all = [...r.field_violations, ...r.competency_violations];
    let warn = 0;
    let miss = 0;
    for (const v of all) {
      if (v.code.includes('mismatch')) warn++;
      else miss++;
    }
    return { ok: 0, warn, miss };
  }
}

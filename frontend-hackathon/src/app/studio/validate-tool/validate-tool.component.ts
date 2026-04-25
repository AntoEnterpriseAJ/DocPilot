import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CaseStore, CaseDocument } from '../case.store';
import { SyncCheckService } from '../../sync-check/services/sync-check.service';
import {
  BibliographyReport,
  ExtractedDocument,
  NumericConsistencyReport,
  StructuralValidationResult,
} from '../../sync-check/models/sync.models';
import { forkJoin, of, switchMap } from 'rxjs';

interface ValidationResult {
  numeric: NumericConsistencyReport;
  biblio: BibliographyReport;
  structural: StructuralValidationResult;
}

@Component({
  selector: 'app-validate-tool',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './validate-tool.component.html',
  styleUrl: './validate-tool.component.scss',
})
export class ValidateToolComponent {
  private readonly store = inject(CaseStore);
  private readonly service = inject(SyncCheckService);

  protected readonly fdId = signal<string | null>(null);
  protected readonly running = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<ValidationResult | null>(null);

  protected readonly fdOptions = computed(() => this.store.documentsByKind().fd);

  constructor() {
    queueMicrotask(() => {
      if (!this.fdId() && this.fdOptions()[0]) this.fdId.set(this.fdOptions()[0].id);
    });
  }

  protected canRun(): boolean {
    return !!this.fdId() && !this.running();
  }

  protected onPickFd(e: Event): void {
    this.fdId.set((e.target as HTMLSelectElement).value || null);
  }

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
    if (!fd) return;

    this.error.set(null);
    this.result.set(null);
    this.running.set(true);

    this.getParsed(fd)
      .pipe(
        switchMap((parsed) =>
          forkJoin({
            numeric: this.service.checkNumericConsistency(parsed),
            biblio: this.service.checkFdBibliography(parsed, {}),
            structural: this.service.validateStructure(parsed),
          }),
        ),
      )
      .subscribe({
        next: (res) => {
          this.running.set(false);
          this.result.set(res);
          this.store.setDocumentStatus(fd.id, { validated: true });
          this.store.setToolResult('validate', res);
        },
        error: (err) => {
          this.running.set(false);
          this.error.set(err?.error?.detail || err?.message || 'Validation failed');
        },
      });
  }

  protected score(): number | null {
    const r = this.result();
    if (!r) return null;
    const numericTotal = r.numeric.total_checks || 1;
    const numericPassed = r.numeric.passed;
    const biblioTotal = r.biblio.total_entries || 1;
    const biblioPassed = r.biblio.fresh_entries;
    const structuralTotal = Object.keys({
      denumirea_disciplinei: 1, titularul_activitatilor_de_curs: 1,
      titularul_activitatilor_de_seminar_laborator_proiect: 1,
      obiective_generale_ale_disciplinei: 1, competente_profesionale: 1,
      competente_transversale: 1, semestrul: 1, anul_de_studiu: 1,
      numar_credite: 1, tipul_de_evaluare: 1,
    }).length;
    const structuralPassed = structuralTotal - r.structural.violations.filter(v => v.code === 'field_required').length;
    const ratio =
      (numericPassed + biblioPassed + structuralPassed) /
      (numericTotal + biblioTotal + structuralTotal);
    return Math.round(ratio * 10 * 10) / 10;
  }
}

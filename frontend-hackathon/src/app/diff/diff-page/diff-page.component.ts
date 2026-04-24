/**
 * DiffPageComponent - main page that orchestrates visual diff components.
 */

import { Component, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { DiffService } from '../services/diff.service';
import { DiffUploadComponent } from '../components/diff-upload/diff-upload.component';

@Component({
  selector: 'app-diff-page',
  standalone: true,
  imports: [
    CommonModule,
    DiffUploadComponent
  ],
  templateUrl: './diff-page.component.html',
  styleUrls: ['./diff-page.component.scss']
})
export class DiffPageComponent implements OnInit {
  // Signals
  visualState = signal<'idle' | 'loading' | 'done' | 'error'>('idle');
  visualResult = signal<{ oldPdf: SafeResourceUrl; newPdf: SafeResourceUrl } | null>(null);
  errorMessage = signal<string | null>(null);
  serviceOnline = signal<boolean | null>(null);

  constructor(private diffService: DiffService, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.diffService.health().subscribe({
      next: () => this.serviceOnline.set(true),
      error: () => {
        this.serviceOnline.set(false);
        console.warn('Diff service not available');
      }
    });
  }

  onFilesSelected(files: { fileOld: File; fileNew: File }) {
    this.visualState.set('loading');
    this.errorMessage.set(null);
    this.visualResult.set(null);

    this.diffService.visualCompare(files.fileOld, files.fileNew).subscribe({
      next: (res) => {
        const oldUrl = this.sanitizer.bypassSecurityTrustResourceUrl('data:application/pdf;base64,' + res.annotated_old_pdf_base64);
        const newUrl = this.sanitizer.bypassSecurityTrustResourceUrl('data:application/pdf;base64,' + res.annotated_new_pdf_base64);
        this.visualResult.set({ oldPdf: oldUrl, newPdf: newUrl });
        this.visualState.set('done');
      },
      error: (err) => {
        console.error('Visual Diff error:', err);
        this.errorMessage.set('Failed to generate visual diff');
        this.visualState.set('error');
      }
    });
  }

  resetResults() {
    this.visualResult.set(null);
    this.visualState.set('idle');
    this.errorMessage.set(null);
  }
}


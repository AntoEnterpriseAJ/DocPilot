/**
 * DiffViewerComponent - displays diffs in GitHub Desktop–style unified format.
 */

import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SectionDiff, LineDiff } from '../../models/diff.models';

@Component({
  selector: 'app-diff-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './diff-viewer.component.html',
  styleUrls: ['./diff-viewer.component.scss']
})
export class DiffViewerComponent {
  sectionDiffs = input<SectionDiff[]>([]);

  /** CSS class for each diff row */
  getRowClass(line: LineDiff): string {
    switch (line.type) {
      case 'add':     return 'row-add';
      case 'remove':  return 'row-remove';
      case 'replace': return 'row-replace';
      default:        return 'row-equal';
    }
  }

  trackBySection(index: number): number { return index; }
  trackByLine(index: number): number    { return index; }
}

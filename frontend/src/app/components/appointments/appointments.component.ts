// frontend/src/app/components/appointments/appointments.component.ts
import { Component, OnInit } from '@angular/core';
import { ApiService, Appointment } from '../../services/api.service';

@Component({
  selector: 'app-appointments',
  templateUrl: './appointments.component.html',
  styleUrls: ['./appointments.component.css']
})
export class AppointmentsComponent implements OnInit {
  appointments: Appointment[] = [];
  filteredAppointments: Appointment[] = [];
  loading = false;
  error: string | null = null;
  
  // Filter options
  filterStatus: string = 'all';
  filterDate: string = 'all';
  searchTerm: string = '';

  // Stats
  stats = {
    total: 0,
    pending: 0,
    confirmed: 0,
    cancelled: 0,
    completed: 0
  };

  // View mode
  viewMode: 'list' | 'calendar' = 'list';

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadAppointments();
  }

  /**
   * Load all appointments
   */
  loadAppointments(): void {
    this.loading = true;
    this.error = null;

    this.apiService.getAppointments().subscribe({
      next: (appointments) => {
        this.appointments = appointments;
        this.filteredAppointments = appointments;
        this.calculateStats();
        this.applyFilters();
        this.loading = false;
      },
      error: (error) => {
        this.error = 'Failed to load appointments: ' + error.message;
        this.loading = false;
        console.error('Error loading appointments:', error);
      }
    });
  }

  /**
   * Calculate statistics
   */
  calculateStats(): void {
    this.stats.total = this.appointments.length;
    this.stats.pending = this.appointments.filter(a => a.status === 'pending').length;
    this.stats.confirmed = this.appointments.filter(a => a.status === 'confirmed').length;
    this.stats.cancelled = this.appointments.filter(a => a.status === 'cancelled').length;
    this.stats.completed = this.appointments.filter(a => a.status === 'completed').length;
  }

  /**
   * Apply filters to appointments
   */
  applyFilters(): void {
    let filtered = [...this.appointments];

    // Filter by status
    if (this.filterStatus !== 'all') {
      filtered = filtered.filter(a => a.status === this.filterStatus);
    }

    // Filter by date
    const now = new Date();
    if (this.filterDate === 'today') {
      filtered = filtered.filter(a => {
        const appointmentDate = new Date(a.scheduled_date);
        return appointmentDate.toDateString() === now.toDateString();
      });
    } else if (this.filterDate === 'upcoming') {
      filtered = filtered.filter(a => {
        const appointmentDate = new Date(a.scheduled_date);
        return appointmentDate >= now;
      });
    } else if (this.filterDate === 'past') {
      filtered = filtered.filter(a => {
        const appointmentDate = new Date(a.scheduled_date);
        return appointmentDate < now;
      });
    }

    // Search filter
    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      filtered = filtered.filter(a =>
        a.service_type.toLowerCase().includes(term) ||
        a.client_id.toLowerCase().includes(term) ||
        (a.notes && a.notes.toLowerCase().includes(term))
      );
    }

    // Sort by date (most recent first)
    filtered.sort((a, b) => {
      return new Date(b.scheduled_date).getTime() - new Date(a.scheduled_date).getTime();
    });

    this.filteredAppointments = filtered;
  }

  /**
   * Change filter status
   */
  onFilterStatusChange(status: string): void {
    this.filterStatus = status;
    this.applyFilters();
  }

  /**
   * Change filter date
   */
  onFilterDateChange(dateFilter: string): void {
    this.filterDate = dateFilter;
    this.applyFilters();
  }

  /**
   * Handle search
   */
  onSearch(): void {
    this.applyFilters();
  }

  /**
   * Clear filters
   */
  clearFilters(): void {
    this.filterStatus = 'all';
    this.filterDate = 'all';
    this.searchTerm = '';
    this.applyFilters();
  }

  /**
   * Confirm appointment
   */
  confirmAppointment(appointment: Appointment): void {
    if (confirm(`Confirm appointment for ${this.formatDate(appointment.scheduled_date)}?`)) {
      this.apiService.updateAppointment(appointment.id, { status: 'confirmed' }).subscribe({
        next: (updated) => {
          this.updateAppointmentInList(updated);
          console.log('Appointment confirmed');
        },
        error: (error) => {
          alert('Failed to confirm appointment: ' + error.message);
        }
      });
    }
  }

  /**
   * Cancel appointment
   */
  cancelAppointment(appointment: Appointment): void {
    if (confirm(`Cancel appointment for ${this.formatDate(appointment.scheduled_date)}?`)) {
      this.apiService.cancelAppointment(appointment.id).subscribe({
        next: () => {
          // Remove from list or update status
          const index = this.appointments.findIndex(a => a.id === appointment.id);
          if (index > -1) {
            this.appointments[index].status = 'cancelled';
            this.calculateStats();
            this.applyFilters();
          }
          console.log('Appointment cancelled');
        },
        error: (error) => {
          alert('Failed to cancel appointment: ' + error.message);
        }
      });
    }
  }

  /**
   * Complete appointment
   */
  completeAppointment(appointment: Appointment): void {
    this.apiService.updateAppointment(appointment.id, { status: 'completed' }).subscribe({
      next: (updated) => {
        this.updateAppointmentInList(updated);
        console.log('Appointment marked as completed');
      },
      error: (error) => {
        alert('Failed to complete appointment: ' + error.message);
      }
    });
  }

  /**
   * Update appointment in list
   */
  private updateAppointmentInList(updated: Appointment): void {
    const index = this.appointments.findIndex(a => a.id === updated.id);
    if (index > -1) {
      this.appointments[index] = updated;
      this.calculateStats();
      this.applyFilters();
    }
  }

  /**
   * Toggle view mode
   */
  toggleViewMode(): void {
    this.viewMode = this.viewMode === 'list' ? 'calendar' : 'list';
  }

  /**
   * Refresh appointments
   */
  refresh(): void {
    this.loadAppointments();
  }

  /**
   * Format date for display
   */
  formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Format time only
   */
  formatTime(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Get status badge class
   */
  getStatusClass(status: string): string {
    const classes: { [key: string]: string } = {
      'pending': 'status-pending',
      'confirmed': 'status-confirmed',
      'cancelled': 'status-cancelled',
      'completed': 'status-completed'
    };
    return classes[status] || 'status-default';
  }

  /**
   * Check if appointment is today
   */
  isToday(dateString: string): boolean {
    const date = new Date(dateString);
    const today = new Date();
    return date.toDateString() === today.toDateString();
  }

  /**
   * Check if appointment is upcoming
   */
  isUpcoming(dateString: string): boolean {
    const date = new Date(dateString);
    const now = new Date();
    return date > now;
  }

  /**
   * Check if appointment is past
   */
  isPast(dateString: string): boolean {
    const date = new Date(dateString);
    const now = new Date();
    return date < now;
  }

  /**
   * Get relative time (e.g., "2 hours ago", "in 3 days")
   */
  getRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60 && diffMins > -60) {
      return diffMins > 0 ? `in ${diffMins} minutes` : `${Math.abs(diffMins)} minutes ago`;
    } else if (diffHours < 24 && diffHours > -24) {
      return diffHours > 0 ? `in ${diffHours} hours` : `${Math.abs(diffHours)} hours ago`;
    } else {
      return diffDays > 0 ? `in ${diffDays} days` : `${Math.abs(diffDays)} days ago`;
    }
  }

  /**
   * Export appointments to CSV
   */
  exportToCSV(): void {
    const headers = ['ID', 'Client ID', 'Service', 'Date', 'Duration', 'Status', 'Notes'];
    const rows = this.filteredAppointments.map(a => [
      a.id,
      a.client_id,
      a.service_type,
      this.formatDate(a.scheduled_date),
      `${a.duration_minutes} min`,
      a.status,
      a.notes || ''
    ]);

    let csvContent = headers.join(',') + '\n';
    rows.forEach(row => {
      csvContent += row.map(cell => `"${cell}"`).join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `appointments_${new Date().toISOString()}.csv`;
    link.click();
    window.URL.revokeObjectURL(url);
  }
}
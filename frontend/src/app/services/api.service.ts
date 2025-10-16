// frontend/src/app/services/api.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, retry, map } from 'rxjs/operators';

export interface Client {
  id: string;
  name: string;
  email: string;
  phone?: string;
  preferences?: any;
  last_appointment_date?: string;
  created_at: string;
  updated_at: string;
}

export interface Appointment {
  id: number;
  client_id: string;
  service_type: string;
  scheduled_date: string;
  duration_minutes: number;
  status: string;
  notes?: string;
  reminder_sent: boolean;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: number;
  client_id: string;
  started_at: string;
  ended_at?: string;
  status: string;
  initiated_by: string;
  summary?: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  content: string;
  sender_type: string;
  timestamp: string;
  metadata?: any;
}

export interface SchedulingRequest {
  client_id: string;
  service_type: string;
  preferred_date: string;
  duration_minutes: number;
  preferences?: any;
}

export interface SchedulingResponse {
  available_slots: Array<{
    datetime: string;
    time: string;
    available: boolean;
  }>;
  ai_suggestions: Array<{
    time: string;
    reason: string;
    score: number;
  }>;
  message: string;
}

export interface HealthCheck {
  status: string;
  timestamp: string;
  service: string;
  ai_status?: string;
}

export interface Stats {
  total_clients: number;
  total_appointments: number;
  pending_appointments: number;
  confirmed_appointments: number;
  active_conversations: number;
  timestamp: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  /**
   * Error handler
   */
  private handleError(error: HttpErrorResponse) {
    let errorMessage = 'An error occurred';
    
    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Error: ${error.error.message}`;
    } else {
      // Server-side error
      errorMessage = `Error Code: ${error.status}\nMessage: ${error.message}`;
      
      if (error.error && error.error.detail) {
        errorMessage += `\nDetails: ${error.error.detail}`;
      }
    }
    
    console.error(errorMessage);
    return throwError(() => new Error(errorMessage));
  }

  // ============ Health Check ============

  healthCheck(): Observable<HealthCheck> {
    return this.http.get<HealthCheck>(`${this.baseUrl}/health`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getStats(): Observable<Stats> {
    return this.http.get<Stats>(`${this.baseUrl}/stats`)
      .pipe(
        catchError(this.handleError)
      );
  }

  // ============ Client Operations ============

  getClient(clientId: string): Observable<Client> {
    return this.http.get<Client>(`${this.baseUrl}/clients/${clientId}`)
      .pipe(
        retry(2),
        catchError(this.handleError)
      );
  }

  // ============ Appointment Operations ============

  getAppointments(params?: {
    client_id?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
  }): Observable<Appointment[]> {
    let httpParams = new HttpParams();
    
    if (params) {
      if (params.client_id) httpParams = httpParams.set('client_id', params.client_id);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.start_date) httpParams = httpParams.set('start_date', params.start_date);
      if (params.end_date) httpParams = httpParams.set('end_date', params.end_date);
    }

    return this.http.get<Appointment[]>(`${this.baseUrl}/appointments`, { params: httpParams })
      .pipe(
        retry(2),
        catchError(this.handleError)
      );
  }

  createAppointment(appointment: {
    client_id: string;
    service_type: string;
    scheduled_date: string;
    duration_minutes: number;
    notes?: string;
  }): Observable<Appointment> {
    return this.http.post<Appointment>(`${this.baseUrl}/appointments`, appointment)
      .pipe(
        catchError(this.handleError)
      );
  }

  updateAppointment(
    appointmentId: number,
    updates: {
      status?: string;
      scheduled_date?: string;
    }
  ): Observable<Appointment> {
    let httpParams = new HttpParams();
    if (updates.status) httpParams = httpParams.set('status', updates.status);
    if (updates.scheduled_date) httpParams = httpParams.set('scheduled_date', updates.scheduled_date);

    return this.http.patch<Appointment>(
      `${this.baseUrl}/appointments/${appointmentId}`,
      null,
      { params: httpParams }
    ).pipe(
      catchError(this.handleError)
    );
  }

  cancelAppointment(appointmentId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/appointments/${appointmentId}`)
      .pipe(
        catchError(this.handleError)
      );
  }

  // ============ Conversation Operations ============

  getConversations(clientId: string, limit: number = 10): Observable<Conversation[]> {
    const httpParams = new HttpParams().set('limit', limit.toString());
    
    return this.http.get<Conversation[]>(
      `${this.baseUrl}/conversations/${clientId}`,
      { params: httpParams }
    ).pipe(
      retry(2),
      catchError(this.handleError)
    );
  }

  getMessages(conversationId: number): Observable<Message[]> {
    return this.http.get<Message[]>(`${this.baseUrl}/messages/${conversationId}`)
      .pipe(
        retry(2),
        catchError(this.handleError)
      );
  }

  // ============ Scheduling Operations ============

  requestScheduling(request: SchedulingRequest): Observable<SchedulingResponse> {
    return this.http.post<SchedulingResponse>(`${this.baseUrl}/scheduling/request`, request)
      .pipe(
        catchError(this.handleError)
      );
  }

  // ============ Utility Methods ============

  /**
   * Get appointments for today
   */
  getTodayAppointments(clientId?: string): Observable<Appointment[]> {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    return this.getAppointments({
      client_id: clientId,
      start_date: today.toISOString(),
      end_date: tomorrow.toISOString()
    });
  }

  /**
   * Get upcoming appointments
   */
  getUpcomingAppointments(clientId?: string, days: number = 7): Observable<Appointment[]> {
    const today = new Date();
    const future = new Date(today);
    future.setDate(future.getDate() + days);

    return this.getAppointments({
      client_id: clientId,
      start_date: today.toISOString(),
      end_date: future.toISOString(),
      status: 'confirmed'
    });
  }

  /**
   * Get pending appointments
   */
  getPendingAppointments(clientId?: string): Observable<Appointment[]> {
    return this.getAppointments({
      client_id: clientId,
      status: 'pending'
    });
  }

  /**
   * Format date for API
   */
  formatDateForApi(date: Date): string {
    return date.toISOString();
  }

  /**
   * Parse date from API
   */
  parseDateFromApi(dateString: string): Date {
    return new Date(dateString);
  }

  /**
   * Check if service is healthy
   */
  async checkHealth(): Promise<boolean> {
    try {
      const health = await this.healthCheck().toPromise();
      return health?.status === 'healthy';
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }
}
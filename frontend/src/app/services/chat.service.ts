// frontend/src/app/services/chat.service.ts
import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private ws: WebSocket | null = null;
  private messagesSubject = new Subject<any>();
  private connectionStatusSubject = new Subject<boolean>();

  constructor() {}

  connect(clientId: string): void {
    // Close existing connection if any
    if (this.ws) {
      this.ws.close();
    }

    // Create new WebSocket connection
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.connectionStatusSubject.next(true);
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.messagesSubject.next(data);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.connectionStatusSubject.next(false);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.connectionStatusSubject.next(false);
      
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        console.log('Attempting to reconnect...');
        this.connect(clientId);
      }, 3000);
    };
  }

  sendMessage(message: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const messageData = {
        content: message,
        timestamp: new Date().toISOString()
      };
      this.ws.send(JSON.stringify(messageData));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  getMessages(): Observable<any> {
    return this.messagesSubject.asObservable();
  }

  getConnectionStatus(): Observable<boolean> {
    return this.connectionStatusSubject.asObservable();
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
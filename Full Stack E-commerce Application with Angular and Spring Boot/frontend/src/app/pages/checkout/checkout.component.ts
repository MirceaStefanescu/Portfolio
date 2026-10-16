import { CurrencyPipe, NgFor, NgIf } from '@angular/common';
import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DEFAULT_CURRENCY, STRIPE_PUBLISHABLE_KEY } from '../../core/config/app-config';
import { OrderResponse } from '../../core/models/order';
import { CartService } from '../../core/services/cart.service';
import { OrderService } from '../../core/services/order.service';

declare const Stripe: (key: string) => any;

@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [CurrencyPipe, NgFor, NgIf, RouterLink],
  templateUrl: './checkout.component.html',
  styleUrl: './checkout.component.css'
})
export class CheckoutComponent implements OnInit, OnDestroy {
  private cartService = inject(CartService);
  private orderService = inject(OrderService);

  readonly demoMode = !STRIPE_PUBLISHABLE_KEY || STRIPE_PUBLISHABLE_KEY === 'pk_test_replace_me';

  status = signal<'idle' | 'loading' | 'ready' | 'processing' | 'success' | 'error'>('idle');
  errorMessage = signal<string | null>(null);
  fatalError = signal(false);

  items = this.cartService.items;
  order = signal<OrderResponse | null>(null);
  summaryItems = computed(() => this.order()?.items ?? this.items().map((item) => ({
    productId: item.product.id,
    name: item.product.name,
    quantity: item.quantity,
    unitPrice: item.product.price
  })));
  currency = computed(() => (this.order()?.currency ?? DEFAULT_CURRENCY).toUpperCase());
  total = computed(() => this.order()?.totalAmount ?? this.items().reduce(
    (sum, item) => sum + item.product.price * item.quantity, 0
  ));

  private stripe: any;
  private card: any;
  private clientSecret: string | null = null;
  private orderId: number | null = null;
  private paymentIntentId: string | null = null;

  async ngOnInit(): Promise<void> {
    if (!this.items().length) {
      this.status.set('error');
      this.fatalError.set(true);
      this.errorMessage.set('Your cart is empty.');
      return;
    }

    if (!this.demoMode && typeof Stripe === 'undefined') {
      this.status.set('loading');
      try {
        await new Promise<void>((resolve, reject) => {
          const script = document.createElement('script');
          script.src = 'https://js.stripe.com/v3/';
          script.onload = () => resolve();
          script.onerror = () => { script.remove(); reject(new Error('Stripe.js failed to load.')); };
          document.head.appendChild(script);
        });
      } catch {
        this.status.set('error');
        this.fatalError.set(true);
        this.errorMessage.set('Stripe.js failed to load.');
        return;
      }
    }

    this.status.set('loading');

    const payload = {
      items: this.items().map((item) => ({
        productId: item.product.id,
        quantity: item.quantity
      })),
      currency: DEFAULT_CURRENCY
    };

    this.orderService.createOrder(payload).subscribe({
      next: (order) => {
        this.order.set(order);
        this.orderId = order.id;
        this.paymentIntentId = order.paymentIntentId ?? null;
        this.clientSecret = order.clientSecret ?? null;
        if (!this.demoMode) {
          if (!this.clientSecret) {
            this.status.set('error');
            this.fatalError.set(true);
            this.errorMessage.set('Stripe client secret was not returned.');
            return;
          }
          this.initStripe();
        }
        this.status.set('ready');
      },
      error: (error) => {
        this.status.set('error');
        this.fatalError.set(true);
        this.errorMessage.set(error?.error?.message ?? 'Unable to start checkout.');
      }
    });
  }

  async pay(): Promise<void> {
    this.status.set('processing');
    this.errorMessage.set(null);

    if (this.demoMode) {
      if (!this.orderId || !this.paymentIntentId) {
        this.status.set('error');
        this.errorMessage.set('Payment intent was not returned.');
        return;
      }

      this.orderService.confirmPayment(this.orderId, this.paymentIntentId).subscribe({
        next: (order) => {
          this.order.set(order);
          this.status.set('success');
          this.cartService.clear();
        },
        error: () => {
          this.status.set('error');
          this.errorMessage.set('Order could not be updated.');
        }
      });
      return;
    }

    if (!this.stripe || !this.card || !this.clientSecret || !this.orderId) {
      return;
    }

    const result = await this.stripe.confirmCardPayment(this.clientSecret, {
      payment_method: {
        card: this.card
      }
    });

    if (result.error) {
      this.status.set('error');
      this.errorMessage.set(result.error.message ?? 'Payment failed.');
      return;
    }

    const paymentIntent = result.paymentIntent;
    if (!paymentIntent) {
      this.status.set('error');
      this.errorMessage.set('Payment intent was not returned.');
      return;
    }

    this.orderService.confirmPayment(this.orderId, paymentIntent.id).subscribe({
      next: (order) => {
        this.order.set(order);
        this.status.set('success');
        this.cartService.clear();
      },
      error: () => {
        this.status.set('error');
        this.errorMessage.set('Payment succeeded, but the order could not be updated.');
      }
    });
  }

  ngOnDestroy(): void {
    if (this.card) {
      this.card.destroy();
    }
  }

  private initStripe(): void {
    this.stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
    const elements = this.stripe.elements();
    this.card = elements.create('card');
    this.card.mount('#card-element');
  }
}

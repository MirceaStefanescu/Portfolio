import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { CheckoutComponent } from './checkout.component';
import { CartService } from '../../core/services/cart.service';
import { OrderService } from '../../core/services/order.service';
import { CartItem } from '../../core/models/cart-item';
import { OrderResponse } from '../../core/models/order';

const receipt: OrderResponse = {
  id: 7, status: 'PAID', totalAmount: 19.5, currency: 'usd',
  paymentIntentId: 'pi_demo', createdAt: '2026-01-01T00:00:00Z',
  items: [{ productId: 1, name: 'Server-priced product', quantity: 2, unitPrice: 9.75 }]
};

describe('checkout receipt', () => {
  const items = signal<CartItem[]>([]);
  const confirmPayment = vi.fn();
  const clear = vi.fn(() => items.set([]));

  beforeEach(async () => {
    vi.clearAllMocks();
    items.set([{ product: { id: 1, name: 'Cached product', price: 10, description: '' }, quantity: 2 }]);
    confirmPayment.mockReturnValue(of(receipt));
    await TestBed.configureTestingModule({
      imports: [CheckoutComponent],
      providers: [provideRouter([]),
        { provide: CartService, useValue: { items, clear } },
        { provide: OrderService, useValue: {
          createOrder: () => of({ ...receipt, status: 'PENDING' }), confirmPayment
        } }
      ]
    }).compileComponents();
  });

  it('retains server-confirmed lines and total after clearing the cart', async () => {
    const fixture = TestBed.createComponent(CheckoutComponent);
    await fixture.whenStable();
    await fixture.componentInstance.pay();
    await fixture.whenStable();
    expect(items()).toEqual([]);
    expect(clear).toHaveBeenCalledOnce();
    expect(fixture.componentInstance.status()).toBe('success');
    const view = fixture.nativeElement as HTMLElement;
    expect(view.querySelector('.summary')?.textContent).toContain('Server-priced product x 2');
    expect(view.querySelector('.total')?.textContent).toContain('$19.50');
    expect(view.querySelector('.summary')?.textContent).not.toContain('Cached product');
  });

  it('keeps the cart and reports a failed confirmation without a success receipt', async () => {
    confirmPayment.mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(CheckoutComponent);
    await fixture.whenStable();
    await fixture.componentInstance.pay();
    await fixture.whenStable();
    expect(clear).not.toHaveBeenCalled();
    expect(items()).toHaveLength(1);
    expect(fixture.componentInstance.status()).toBe('error');
    expect(fixture.nativeElement.querySelector('.success')).toBeNull();
  });

  it('also preserves the confirmed receipt after the Stripe payment path', async () => {
    const fixture = TestBed.createComponent(CheckoutComponent);
    await fixture.whenStable();
    const component = fixture.componentInstance;
    Object.assign(component, {
      demoMode: false, card: { destroy: vi.fn() }, clientSecret: 'test-only-intent',
      stripe: { confirmCardPayment: vi.fn().mockResolvedValue({ paymentIntent: { id: 'pi_demo' } }) }
    });
    await component.pay();
    await fixture.whenStable();
    expect(confirmPayment).toHaveBeenCalledWith(7, 'pi_demo');
    expect(items()).toEqual([]);
    expect(component.total()).toBe(19.5);
    expect(fixture.nativeElement.querySelector('.total')?.textContent).toContain('$19.50');
  });
});

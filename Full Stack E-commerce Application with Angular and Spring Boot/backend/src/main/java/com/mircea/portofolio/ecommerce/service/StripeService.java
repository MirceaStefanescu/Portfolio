package com.mircea.portofolio.ecommerce.service;

import com.stripe.exception.StripeException;
import com.stripe.model.PaymentIntent;
import com.stripe.net.RequestOptions;
import com.stripe.param.PaymentIntentCreateParams;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class StripeService {
    private final RequestOptions options;
    private final boolean mockEnabled;

    public StripeService(
            @Value("${stripe.secret-key:}") String secretKey,
            @Value("${stripe.mock-enabled:false}") boolean mockEnabled) {
        this.options = secretKey == null || secretKey.isBlank()
                ? null : RequestOptions.builder().setApiKey(secretKey).build();
        this.mockEnabled = mockEnabled;
    }

    public StripePaymentIntent createPaymentIntent(long amount, String currency, Long orderId) throws StripeException {
        if (options == null) {
            requireMockMode();
            String id = "mock_pi_" + UUID.randomUUID().toString().replace("-", "");
            return new StripePaymentIntent(id, "mock_secret_" + UUID.randomUUID(), "requires_payment_method");
        }
        PaymentIntentCreateParams params = PaymentIntentCreateParams.builder()
                .setAmount(amount)
                .setCurrency(currency)
                .setAutomaticPaymentMethods(PaymentIntentCreateParams.AutomaticPaymentMethods.builder()
                        .setEnabled(true).build())
                .putMetadata("orderId", String.valueOf(orderId))
                .build();
        PaymentIntent intent = PaymentIntent.create(params, options);
        return new StripePaymentIntent(intent.getId(), intent.getClientSecret(), intent.getStatus());
    }

    public StripePaymentIntent retrievePaymentIntent(String paymentIntentId) throws StripeException {
        if (options == null) {
            requireMockMode();
            // Persisted real Stripe intents must never become simulated successes.
            if (paymentIntentId == null || !paymentIntentId.matches("mock_pi_[a-f0-9]{32}")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Not a demo payment intent");
            }
            return new StripePaymentIntent(paymentIntentId, null, "succeeded");
        }
        PaymentIntent intent = PaymentIntent.retrieve(paymentIntentId, options);
        return new StripePaymentIntent(intent.getId(), intent.getClientSecret(), intent.getStatus());
    }

    private void requireMockMode() {
        if (!mockEnabled) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Payments are not configured");
        }
    }
}

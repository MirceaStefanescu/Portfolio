package com.mircea.portofolio.ecommerce.service;

import com.mircea.portofolio.ecommerce.dto.CreateOrderRequest;
import com.mircea.portofolio.ecommerce.dto.OrderItemRequest;
import com.mircea.portofolio.ecommerce.dto.OrderResponse;
import com.mircea.portofolio.ecommerce.model.Order;
import com.mircea.portofolio.ecommerce.model.OrderItem;
import com.mircea.portofolio.ecommerce.model.OrderStatus;
import com.mircea.portofolio.ecommerce.model.Product;
import com.mircea.portofolio.ecommerce.model.User;
import com.mircea.portofolio.ecommerce.repository.OrderRepository;
import com.mircea.portofolio.ecommerce.repository.ProductRepository;
import com.mircea.portofolio.ecommerce.repository.UserRepository;
import com.stripe.exception.StripeException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OrderService {
	private final OrderRepository orderRepository;
	private final ProductRepository productRepository;
	private final UserRepository userRepository;
	private final StripeService stripeService;

	public OrderService(
			OrderRepository orderRepository,
			ProductRepository productRepository,
			UserRepository userRepository,
			StripeService stripeService
	) {
		this.orderRepository = orderRepository;
		this.productRepository = productRepository;
		this.userRepository = userRepository;
		this.stripeService = stripeService;
	}

	@Transactional
	public OrderResponse createOrder(String userEmail, CreateOrderRequest request) {
		User user = userRepository.findByEmail(userEmail)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));

		if (request.items() == null || request.items().isEmpty()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Order must include at least one item");
		}

		String currency = normalizeCurrency(request.currency());

		List<Long> productIds = request.items().stream()
				.map(OrderItemRequest::productId)
				.distinct()
				.toList();

		Map<Long, Product> products = productRepository.findAllById(productIds).stream()
				.collect(Collectors.toMap(Product::getId, Function.identity()));

		if (products.size() != productIds.size()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Some products were not found");
		}

		Order order = new Order();
		order.setUser(user);
		order.setCurrency(currency);

		BigDecimal total = BigDecimal.ZERO;
		for (OrderItemRequest itemRequest : request.items()) {
			if (itemRequest.quantity() < 1) {
				throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Quantity must be at least 1");
			}
			Product product = products.get(itemRequest.productId());
			if (product == null || !product.isActive()) {
				throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Product not found");
			}
			OrderItem item = new OrderItem();
			item.setProduct(product);
			item.setQuantity(itemRequest.quantity());
			item.setUnitPrice(product.getPrice());
			order.addItem(item);
			BigDecimal lineTotal = product.getPrice().multiply(BigDecimal.valueOf(itemRequest.quantity()));
			total = total.add(lineTotal);
		}

		if (total.compareTo(BigDecimal.ZERO) <= 0) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Order total must be positive");
		}

		order.setTotalAmount(total);
		order.setStatus(OrderStatus.PENDING);

		orderRepository.save(order);

		long amountInMinor = total.multiply(BigDecimal.valueOf(100))
				.setScale(0, RoundingMode.HALF_UP)
				.longValueExact();

		StripePaymentIntent intent;
		try {
			intent = stripeService.createPaymentIntent(amountInMinor, currency, order.getId());
		} catch (StripeException ex) {
			order.setStatus(OrderStatus.CANCELLED);
			orderRepository.save(order);
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Payment provider request failed", ex);
		}

		order.setPaymentIntentId(intent.id());
		orderRepository.save(order);

		return OrderResponse.from(order, intent.clientSecret());
	}

	@Transactional(readOnly = true)
	public List<OrderResponse> listOrders(String userEmail) {
		List<Order> orders = orderRepository.findByUserEmailOrderByCreatedAtDesc(userEmail);
		return orders.stream()
				.map(order -> OrderResponse.from(order, null))
				.toList();
	}

	@Transactional
	public OrderResponse confirmPayment(String userEmail, Long orderId, String paymentIntentId) {
		Order order = orderRepository.findById(orderId)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Order not found"));

		if (order.getUser() == null || order.getUser().getEmail() == null
				|| !order.getUser().getEmail().equalsIgnoreCase(userEmail)) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Order does not belong to user");
		}

		if (order.getPaymentIntentId() == null || !order.getPaymentIntentId().equals(paymentIntentId)) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Payment intent mismatch");
		}

		if (order.getStatus() == OrderStatus.PAID) {
			return OrderResponse.from(order, null);
		}

		StripePaymentIntent intent;
		try {
			intent = stripeService.retrievePaymentIntent(paymentIntentId);
		} catch (StripeException ex) {
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Payment provider request failed", ex);
		}

		switch (intent.status()) {
			case "succeeded" -> order.setStatus(OrderStatus.PAID);
			case "canceled" -> order.setStatus(OrderStatus.CANCELLED);
			default -> order.setStatus(OrderStatus.PENDING);
		}

		orderRepository.save(order);
		return OrderResponse.from(order, null);
	}

	private String normalizeCurrency(String currency) {
		if (currency == null || currency.isBlank()) {
			return "usd";
		}
        String normalized = currency.trim().toLowerCase(Locale.ROOT);
        if (!"usd".equals(normalized)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Catalog prices are in USD");
        }
        return normalized;
	}
}

package com.mircea.portofolio.ecommerce.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;

public record CreateOrderRequest(
		@NotEmpty List<@NotNull @Valid OrderItemRequest> items,
		String currency
) {}

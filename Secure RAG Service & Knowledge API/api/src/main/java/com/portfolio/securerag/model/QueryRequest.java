package com.portfolio.securerag.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Max;

public record QueryRequest(
        @NotBlank String question,
        @Min(1) @Max(100) Integer topK
) {
}

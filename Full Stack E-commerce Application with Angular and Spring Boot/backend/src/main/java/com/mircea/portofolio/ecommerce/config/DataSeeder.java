package com.mircea.portofolio.ecommerce.config;

import com.mircea.portofolio.ecommerce.model.Product;
import com.mircea.portofolio.ecommerce.repository.ProductRepository;
import java.math.BigDecimal;
import java.util.List;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class DataSeeder implements CommandLineRunner {
	private final ProductRepository productRepository;

	public DataSeeder(ProductRepository productRepository) {
		this.productRepository = productRepository;
	}

	@Override
	public void run(String... args) {
		if (productRepository.count() > 0) {
			return;
		}
		List<Product> products = List.of(
				new Product(
						"Starter Hoodie",
						"Everyday hoodie with soft lining and relaxed fit.",
						new BigDecimal("59.00"),
						"/products/hoodie.svg",
						"Apparel"
				),
				new Product(
						"Desk Essentials Kit",
						"Compact kit with notebook, pen, and cable organizers.",
						new BigDecimal("24.50"),
						"/products/desk.svg",
						"Accessories"
				),
				new Product(
						"Wireless Earbuds",
						"Noise-isolating earbuds with charging case.",
						new BigDecimal("129.99"),
						"/products/earbuds.svg",
						"Electronics"
				)
		);
		productRepository.saveAll(products);
	}
}

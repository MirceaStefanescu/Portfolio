package com.portfolio.securerag.service;

import com.portfolio.securerag.config.RagProperties;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.springframework.stereotype.Service;

@Service
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = "rag.provider", havingValue = "local", matchIfMissing = true)
public class HashEmbeddingService implements EmbeddingService {

    private final RagProperties ragProperties;

    public HashEmbeddingService(RagProperties ragProperties) {
        this.ragProperties = ragProperties;
    }

    @Override
    public float[] embed(String text) {
        int size = ragProperties.getVectorSize();
        float[] vector = new float[size];
        if (text == null || text.isBlank()) {
            return vector;
        }

        String normalized = text.toLowerCase(Locale.ROOT);
        String[] tokens = normalized.split("\\W+");
        for (String token : tokens) {
            if (token.isBlank()) {
                continue;
            }
            int hash = murmur3(token);
            int index = Math.floorMod(hash, size);
            vector[index] += 1.0f;
        }

        float norm = 0.0f;
        for (float value : vector) {
            norm += value * value;
        }
        norm = (float) Math.sqrt(norm);
        if (norm > 0.0f) {
            for (int i = 0; i < vector.length; i++) {
                vector[i] = vector[i] / norm;
            }
        }

        return vector;
    }

    private int murmur3(String token) {
        byte[] data = token.getBytes(StandardCharsets.UTF_8);
        int h1 = 0;
        int c1 = 0xcc9e2d51;
        int c2 = 0x1b873593;
        int length = data.length;
        int roundedEnd = length & 0xfffffffc;

        for (int i = 0; i < roundedEnd; i += 4) {
            int k1 = (data[i] & 0xff)
                    | ((data[i + 1] & 0xff) << 8)
                    | ((data[i + 2] & 0xff) << 16)
                    | ((data[i + 3] & 0xff) << 24);
            k1 *= c1;
            k1 = Integer.rotateLeft(k1, 15);
            k1 *= c2;

            h1 ^= k1;
            h1 = Integer.rotateLeft(h1, 13);
            h1 = h1 * 5 + 0xe6546b64;
        }

        int k1 = 0;
        int tail = length & 0x03;
        if (tail == 3) {
            k1 ^= (data[roundedEnd + 2] & 0xff) << 16;
        }
        if (tail >= 2) {
            k1 ^= (data[roundedEnd + 1] & 0xff) << 8;
        }
        if (tail >= 1) {
            k1 ^= (data[roundedEnd] & 0xff);
            k1 *= c1;
            k1 = Integer.rotateLeft(k1, 15);
            k1 *= c2;
            h1 ^= k1;
        }

        h1 ^= length;
        h1 ^= (h1 >>> 16);
        h1 *= 0x85ebca6b;
        h1 ^= (h1 >>> 13);
        h1 *= 0xc2b2ae35;
        h1 ^= (h1 >>> 16);

        return h1;
    }
}

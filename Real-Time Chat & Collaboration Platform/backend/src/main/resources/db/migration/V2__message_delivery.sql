-- Existing messages were already published. New entity instances explicitly persist false.
alter table chat_messages add column published boolean not null default true;
alter table chat_messages add column client_request_id varchar(64);
create unique index idx_chat_message_request on chat_messages(sender, client_request_id);
create index idx_chat_message_pending on chat_messages(created_at) where published = false;

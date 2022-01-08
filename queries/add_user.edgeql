SELECT(
INSERT User {
    discord_id := <std::bigint>$user_id,
    name := <bounded_str>$user_name,
    discriminator := <bounded_str>('#' ++ $user_discriminator),
    is_bot := <bool>$bot,
}
) {
    id,
    discord_id,
    user_id,
    name,
    full_tag,
    is_owner,
    guilds: {
        name,
        discord_id,
    }
};
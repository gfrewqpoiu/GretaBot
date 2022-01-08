SELECT(
    UPDATE User
    FILTER .discord_id = <std::bigint>$user_id
    SET {
        name := <bounded_str>$user_name,
        discriminator := <bounded_str>('#' ++ $user_discriminator),
    }
) {
    id,
    discord_id,
    user_id,
    name,
    discriminator,
    full_tag,
    is_owner,
    guilds: {
        name,
        discord_id,
    }
};